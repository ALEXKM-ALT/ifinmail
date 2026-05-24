#!/usr/bin/env python3
"""
ifinmail Health Monitor — collects metrics for the deliverability dashboard.
Runs as a cron job every 5 minutes. Pushes metrics to Redis for the API to read.
"""
import subprocess
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

try:
    import redis
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True, socket_connect_timeout=5)
except ImportError:
    redis_client = None


def check_postfix_queue() -> Dict[str, Any]:
    """Check mail queue status."""
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "/opt/ifinmail/provisioning/docker/docker-compose.yml",
             "exec", "-T", "postfix", "find", "/var/spool/postfix/active", "-type", "f"],
            capture_output=True, text=True, timeout=30
        )
        active = len([l for l in result.stdout.strip().split("\n") if l])

        result = subprocess.run(
            ["docker", "compose", "-f", "/opt/ifinmail/provisioning/docker/docker-compose.yml",
             "exec", "-T", "postfix", "find", "/var/spool/postfix/deferred", "-type", "f"],
            capture_output=True, text=True, timeout=30
        )
        deferred = len([l for l in result.stdout.strip().split("\n") if l])

        if deferred < 50:
            status = "OK"
        elif deferred < 200:
            status = "WARN"
        else:
            status = "CRITICAL"

        return {
            "queue_active": active,
            "queue_deferred": deferred,
            "queue_total": active + deferred,
            "status": status,
        }
    except Exception as e:
        return {"error": str(e), "status": "UNKNOWN"}


def check_service_status() -> Dict[str, bool]:
    """Check if all Docker services are running."""
    services = {
        "postgres": "postgres:5432",
        "redis": "redis:6379",
        "postfix": "postfix:25",
        "dovecot": "dovecot:993",
        "rspamd": "rspamd:11332",
        "api": "api:8000",
        "nginx": "nginx:443",
    }
    status = {}
    for name, target in services.items():
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", "/opt/ifinmail/provisioning/docker/docker-compose.yml",
                 "ps", "--status", "running", name],
                capture_output=True, text=True, timeout=10
            )
            # Service is running if its name appears in output
            status[name] = name in result.stdout
        except Exception:
            status[name] = False
    return status


def check_disk_space() -> Dict[str, Any]:
    """Check disk usage."""
    mounts = ["/", "/var", "/backups"]
    result = {}
    for mount in mounts:
        try:
            df = subprocess.check_output(["df", "-h", mount], text=True)
            lines = df.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                result[mount] = {
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "use_pct": parts[4],
                }
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return result


def check_delivery_rate() -> Dict[str, Any]:
    """Calculate delivery rate from Postfix logs (last hour)."""
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "/opt/ifinmail/provisioning/docker/docker-compose.yml",
             "exec", "-T", "postfix", "grep", "-E", "status=(sent|deferred|bounced)",
             "/var/log/mail.log"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

        sent = sum(1 for l in lines if "status=sent" in l)
        deferred = sum(1 for l in lines if "status=deferred" in l)
        bounced = sum(1 for l in lines if "status=bounced" in l)
        total = sent + deferred + bounced

        return {
            "sent": sent,
            "deferred": deferred,
            "bounced": bounced,
            "delivery_rate": round(sent / total * 100, 1) if total > 0 else 100.0,
        }
    except Exception as e:
        return {"error": str(e)}


def check_cert_expiry() -> Dict[str, Any]:
    """Check TLS certificate expiration."""
    mail_hostname = os.getenv("MAIL_HOSTNAME", "mail.example.com")
    cert_paths = [
        f"/etc/letsencrypt/live/{mail_hostname}/fullchain.pem",
    ]
    results = {}
    for path in cert_paths:
        try:
            output = subprocess.check_output(
                ["openssl", "x509", "-in", path, "-noout", "-enddate"],
                text=True, stderr=subprocess.DEVNULL
            )
            expiry_str = output.split("=")[1].strip()
            expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            days_left = (expiry - datetime.now()).days

            if days_left > 30:
                status = "OK"
            elif days_left > 7:
                status = "WARN"
            else:
                status = "CRITICAL"

            results[path] = {
                "expires": expiry.isoformat(),
                "days_left": days_left,
                "status": status,
            }
        except Exception:
            pass
    return results


def run_all_checks() -> Dict[str, Any]:
    """Run all health checks and store in Redis."""
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "postfix_queue": check_postfix_queue(),
        "services": check_service_status(),
        "disk": check_disk_space(),
        "delivery_rate": check_delivery_rate(),
        "certificates": check_cert_expiry(),
    }

    # Determine overall status
    statuses = []
    if isinstance(report["postfix_queue"].get("status"), str):
        statuses.append(report["postfix_queue"]["status"])
    if not all(report["services"].values()):
        statuses.append("CRITICAL")

    if "CRITICAL" in statuses:
        report["overall"] = "CRITICAL"
    elif "WARN" in statuses:
        report["overall"] = "WARN"
    else:
        report["overall"] = "OK"

    # Store in Redis if available
    if redis_client:
        try:
            redis_client.setex("ifinmail:monitor:latest", 600, json.dumps(report))
            redis_client.lpush("ifinmail:monitor:history", json.dumps(report))
            redis_client.ltrim("ifinmail:monitor:history", 0, 287)
        except Exception:
            pass

    return report


if __name__ == "__main__":
    report = run_all_checks()
    print(json.dumps(report, indent=2))

    if report["overall"] == "CRITICAL":
        print("\n!!! CRITICAL — check ifinmail services immediately !!!")
    elif report["overall"] == "WARN":
        print("\n! WARNING — some services need attention")
