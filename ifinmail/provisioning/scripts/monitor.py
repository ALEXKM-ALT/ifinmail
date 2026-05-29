#!/usr/bin/env python3
"""
ifinmail Health Monitor — collects metrics for the deliverability dashboard.
Runs as a cron job every 5 minutes. Pushes metrics to Redis for the API to read.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
MAIL_HOSTNAME = os.environ.get('MAIL_HOSTNAME', '')
CERT_DIR = os.path.join(PROJECT_ROOT, 'provisioning', 'docker', 'certs', 'live', MAIL_HOSTNAME)
COMPOSE_FILE = os.path.join(PROJECT_ROOT, 'provisioning', 'docker', 'docker-compose.yml')
ALERT_WEBHOOK = os.environ.get('MONITOR_ALERT_WEBHOOK', '')
QUEUE_WARN = int(os.environ.get('MONITOR_QUEUE_WARN', '50'))
QUEUE_CRITICAL = int(os.environ.get('MONITOR_QUEUE_CRITICAL', '200'))

# Track alert state to avoid repeated notifications
ALERT_STATE_FILE = os.environ.get('ALERT_STATE_FILE', '/var/lib/ifinmail/alert_state')

try:
    import redis

    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD or None,
        db=0,
        decode_responses=True,
        socket_connect_timeout=5,
    )
except ImportError:
    redis_client = None


def _docker_compose_cmd() -> list[str]:
    """Build the docker compose command with the correct compose file."""
    if os.path.exists('/usr/bin/docker') or os.path.exists('/usr/local/bin/docker'):
        return ['docker', 'compose', '-f', COMPOSE_FILE]
    return ['docker-compose', '-f', COMPOSE_FILE]


def _docker_ps() -> str:
    """Get docker compose ps output in JSON or fallback text."""
    try:
        result = subprocess.run(
            _docker_compose_cmd() + ['ps', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ''


def check_postfix_queue() -> dict[str, Any]:
    """Check mail queue status."""
    try:
        result = subprocess.run(
            _docker_compose_cmd()
            + ['exec', '-T', 'postfix', 'find', '/var/spool/postfix/active', '-type', 'f'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        active = len([line for line in result.stdout.strip().split('\n') if line])

        result = subprocess.run(
            _docker_compose_cmd()
            + ['exec', '-T', 'postfix', 'find', '/var/spool/postfix/deferred', '-type', 'f'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        deferred = len([line for line in result.stdout.strip().split('\n') if line])

        if deferred < QUEUE_WARN:
            status = 'OK'
        elif deferred < QUEUE_CRITICAL:
            status = 'WARN'
        else:
            status = 'CRITICAL'

        return {
            'queue_active': active,
            'queue_deferred': deferred,
            'queue_total': active + deferred,
            'status': status,
        }
    except Exception as e:
        return {'error': str(e), 'status': 'UNKNOWN'}


def check_service_status() -> dict[str, Any]:
    """Check if all Docker services are running using docker compose ps."""
    services = ['postgres', 'redis', 'postfix', 'dovecot', 'rspamd', 'api', 'nginx', 'certbot']
    status = {}

    try:
        result = subprocess.run(
            _docker_compose_cmd() + ['ps', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        running_names = set()
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    entry = json.loads(line)
                    if entry.get('State') == 'running':
                        running_names.add(entry.get('Service', ''))
                except json.JSONDecodeError:
                    pass
        for name in services:
            status[name] = name in running_names
    except Exception:
        for name in services:
            status[name] = False
    return status


def check_disk_space() -> dict[str, Any]:
    """Check disk usage."""
    mounts = os.environ.get('MONITOR_DISK_MOUNTS', '/,/var,/backups').split(',')
    result = {}
    for mount in mounts:
        try:
            df = subprocess.check_output(['df', '-h', mount], text=True)
            lines = df.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                result[mount] = {
                    'size': parts[1],
                    'used': parts[2],
                    'available': parts[3],
                    'use_pct': parts[4],
                }
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return result


def check_delivery_rate() -> dict[str, Any]:
    """Calculate delivery rate from Postfix logs (last hour)."""
    try:
        since_time = (datetime.now(UTC) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        log_filter = (
            f'awk \'$1"T"$2 >= "{since_time}"\' /var/log/mail.log | '
            'grep -E \'status=(sent|deferred|bounced)\''
        )
        result = subprocess.run(
            _docker_compose_cmd() + ['exec', '-T', 'postfix', 'sh', '-c', log_filter],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []

        sent = sum(1 for line in lines if 'status=sent' in line)
        deferred = sum(1 for line in lines if 'status=deferred' in line)
        bounced = sum(1 for line in lines if 'status=bounced' in line)
        total = sent + deferred + bounced

        return {
            'sent': sent,
            'deferred': deferred,
            'bounced': bounced,
            'delivery_rate': round(sent / total * 100, 1) if total > 0 else 100.0,
        }
    except Exception as e:
        return {'error': str(e)}


def check_api_health() -> dict[str, Any]:
    """Check if the API health endpoint responds."""
    try:
        result = subprocess.run(
            ['curl', '-fsS', '-m', '5', 'http://localhost:8000/health/'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {'status': 'degraded', 'error': 'invalid response'}
        return {'status': 'unreachable', 'error': f'HTTP {result.returncode}'}
    except Exception as e:
        return {'status': 'unreachable', 'error': str(e)}


def check_cert_expiry() -> dict[str, Any]:
    """Check TLS certificate expiration on the host filesystem."""
    cert_path = os.path.join(CERT_DIR, 'fullchain.pem')
    if not os.path.exists(cert_path):
        return {'error': f'cert not found at {cert_path}'}

    try:
        output = subprocess.check_output(
            ['openssl', 'x509', '-in', cert_path, '-noout', '-enddate'],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        expiry_str = output.split('=')[1].strip()
        expiry = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
        days_left = (expiry - datetime.now()).days

        cert_warn = int(os.environ.get('MONITOR_CERT_WARN_DAYS', '30'))
        cert_critical = int(os.environ.get('MONITOR_CERT_CRITICAL_DAYS', '7'))

        if days_left > cert_warn:
            status = 'OK'
        elif days_left > cert_critical:
            status = 'WARN'
        else:
            status = 'CRITICAL'

        return {
            'path': cert_path,
            'expires': expiry.isoformat(),
            'days_left': days_left,
            'status': status,
        }
    except Exception as e:
        return {'error': str(e), 'status': 'UNKNOWN'}


def check_system_resources() -> dict[str, Any]:
    """Check CPU and memory usage."""
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return {
            'cpu_percent': cpu,
            'memory_percent': mem.percent,
            'memory_available_gb': round(mem.available / (1024**3), 1),
            'disk_percent': disk.percent,
            'disk_free_gb': round(disk.free / (1024**3), 1),
        }
    except ImportError:
        # Fallback: use /proc
        try:
            with open('/proc/loadavg') as f:
                load = f.read().split()[0]
            with open('/proc/meminfo') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        meminfo[key] = int(val)
                mem_total = meminfo.get('MemTotal', 0)
                mem_avail = meminfo.get('MemAvailable', 0)
                mem_pct = round((1 - mem_avail / mem_total) * 100, 1) if mem_total else 0
            return {
                'load_average': load,
                'memory_percent': mem_pct,
                'method': 'procfs',
            }
        except Exception as e:
            return {'error': str(e)}


def check_backup_freshness() -> dict[str, Any]:
    """Check age of the most recent backup."""
    backup_dir = os.environ.get('BACKUP_DIR', '/backups')
    try:
        if not os.path.isdir(backup_dir):
            return {'status': 'WARN', 'error': f'backup directory {backup_dir} not found'}
        backups = sorted(
            [
                f
                for f in os.listdir(backup_dir)
                if f.startswith('ifinmail_backup_')
                and (f.endswith('.tar.gz') or f.endswith('.tar.gz.gpg'))
            ],
            reverse=True,
        )
        if not backups:
            return {'status': 'WARN', 'error': 'no backup files found'}
        latest = os.path.join(backup_dir, backups[0])
        age_hours = (
            datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest))
        ).total_seconds() / 3600
        max_age = int(os.environ.get('MONITOR_BACKUP_MAX_AGE_HOURS', '25'))
        if age_hours > max_age:
            return {
                'status': 'CRITICAL',
                'latest_backup': backups[0],
                'age_hours': round(age_hours, 1),
            }
        if age_hours > max_age * 0.8:
            return {'status': 'WARN', 'latest_backup': backups[0], 'age_hours': round(age_hours, 1)}
        return {'status': 'OK', 'latest_backup': backups[0], 'age_hours': round(age_hours, 1)}
    except Exception as e:
        return {'status': 'UNKNOWN', 'error': str(e)}


def send_alert(report: dict[str, Any]):
    """Send webhook alert if status is CRITICAL and state changed."""
    if not ALERT_WEBHOOK:
        return

    overall = report.get('overall', 'OK')
    prev_state = None
    try:
        with open(ALERT_STATE_FILE) as f:
            prev_state = f.read().strip()
    except FileNotFoundError:
        pass

    if overall == 'CRITICAL' and prev_state != 'CRITICAL':
        # Send alert
        try:
            payload = json.dumps(
                {
                    'text': (
                        ':red_circle: ifinmail monitor CRITICAL\n```\n'
                        f'{json.dumps(report, indent=2)[:1400]}\n```'
                    )
                }
            )
            subprocess.run(
                [
                    'curl',
                    '-fsS',
                    '-X',
                    'POST',
                    '-H',
                    'Content-Type: application/json',
                    '-d',
                    payload,
                    ALERT_WEBHOOK,
                ],
                timeout=10,
                capture_output=True,
            )
        except Exception:
            pass
    elif overall == 'OK' and prev_state == 'CRITICAL':
        # Recovery notification
        try:
            payload = json.dumps(
                {'text': ':green_circle: ifinmail monitor RECOVERED — all systems OK'}
            )
            subprocess.run(
                [
                    'curl',
                    '-fsS',
                    '-X',
                    'POST',
                    '-H',
                    'Content-Type: application/json',
                    '-d',
                    payload,
                    ALERT_WEBHOOK,
                ],
                timeout=10,
                capture_output=True,
            )
        except Exception:
            pass

    # Persist current state (atomic write)
    try:
        state_dir = os.path.dirname(ALERT_STATE_FILE)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        tmp_path = f'{ALERT_STATE_FILE}.tmp'
        with open(tmp_path, 'w') as f:
            f.write(overall)
        os.replace(tmp_path, ALERT_STATE_FILE)
    except Exception:
        pass


def run_all_checks() -> dict[str, Any]:
    """Run all health checks and store in Redis."""
    report = {
        'timestamp': datetime.now(UTC).isoformat(),
        'postfix_queue': check_postfix_queue(),
        'services': check_service_status(),
        'api_health': check_api_health(),
        'disk': check_disk_space(),
        'delivery_rate': check_delivery_rate(),
        'certificates': check_cert_expiry(),
        'system': check_system_resources(),
        'backups': check_backup_freshness(),
    }

    # Determine overall status
    statuses = []
    if isinstance(report['postfix_queue'].get('status'), str):
        statuses.append(report['postfix_queue']['status'])
    if not all(report['services'].values()):
        statuses.append('CRITICAL')
    api_status = report.get('api_health', {}).get('status', 'unknown')
    if api_status not in ('ok', 'unknown'):
        statuses.append('WARN' if api_status == 'degraded' else 'CRITICAL')
    cert_status = report.get('certificates', {}).get('status', 'OK')
    if cert_status in ('CRITICAL', 'WARN', 'UNKNOWN'):
        statuses.append(cert_status)

    if 'CRITICAL' in statuses:
        report['overall'] = 'CRITICAL'
    elif 'WARN' in statuses or 'UNKNOWN' in statuses:
        report['overall'] = 'WARN'
    else:
        report['overall'] = 'OK'

    # Store in Redis if available
    if redis_client:
        try:
            redis_client.setex('ifinmail:monitor:latest', 600, json.dumps(report))
            redis_client.lpush('ifinmail:monitor:history', json.dumps(report))
            redis_client.ltrim('ifinmail:monitor:history', 0, 287)
        except Exception:
            pass

    # Send alert if needed
    send_alert(report)

    return report


if __name__ == '__main__':
    import fcntl

    LOCKFILE = '/var/lock/ifinmail_monitor.lock'
    lock_dir = os.path.dirname(LOCKFILE)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)
    try:
        lock_fd = os.open(LOCKFILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('Monitor already running, exiting.')
        sys.exit(0)

    try:
        report = run_all_checks()
        print(json.dumps(report, indent=2))
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    if report['overall'] == 'CRITICAL':
        print('\n!!! CRITICAL — check ifinmail services immediately !!!')
        sys.exit(2)
    elif report['overall'] == 'WARN':
        print('\n! WARNING — some services need attention')
        sys.exit(1)
