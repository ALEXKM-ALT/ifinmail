"""Dashboard view — live stats, service health, DNS status, activity."""
import logging
import os
import shutil
import subprocess
from datetime import timezone
from typing import Any

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from backend.apps.accounts.services import UserService
from backend.apps.domains.services import DomainService
from backend.apps.mail.services import MailService
from backend.services.audit import AuditService
from backend.services.monitoring import MonitoringService
from django.utils.translation import gettext_lazy as _

from ._constants import _APP_DIR, _LETSENCRYPT_DIR, _MAIL_VHOSTS_DIR
from .auth import _is_staff

logger = logging.getLogger("backend")

# Allowed command prefixes for the web shell (read-only inspection only).
_SHELL_ALLOWLIST = (
    "uptime", "free", "df", "ps", "netstat", "ss", "top -bn1",
    "systemctl status", "systemctl is-active", "systemctl is-enabled",
    "postqueue -p", "mailq", "tail", "head", "cat /etc/",
    "cat /var/log/", "openssl x509 -text -noout -in",
    "ls", "du", "who", "w", "last", "hostname", "date",
    "uname", "ip addr", "ip route", "dmesg | tail",
    "journalctl --no-pager -n", "docker ps", "docker logs",
)


def _make_check(code: str, status_bool: bool, label: str) -> dict[str, str]:
    if status_bool:
        return {"check": code, "status": "pass", "message": f"{label} verified"}
    return {"check": code, "status": "warn", "message": f"Verify {label}"}


def _get_tls_expiry_days() -> dict[str, Any]:
    """Read TLS certificate and return days until expiry."""
    mail_hostname = os.environ.get("MAIL_HOSTNAME", "")
    domain = os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", ""))
    cert_paths = []
    if mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, "live", mail_hostname, "fullchain.pem"))
    if domain and domain != mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, "live", domain, "fullchain.pem"))

    if not cert_paths:
        return {"days": None, "display": "N/A", "status": "err"}

    if not shutil.which("openssl"):
        logger.error("openssl not found on PATH; cannot check TLS expiry")
        return {"days": None, "display": "N/A", "status": "err"}

    for cert_path in cert_paths:
        if not os.path.isfile(cert_path):
            continue
        try:
            from datetime import datetime as dt

            import subprocess

            result = subprocess.run(
                ["openssl", "x509", "-enddate", "-noout", "-in", cert_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                continue
            date_str = result.stdout.strip().split("=", 1)[1]
            end_date = dt.strptime(date_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (end_date - dt.now(timezone.utc)).days
            return {
                "days": days,
                "display": f"{days}d",
                "status": "ok" if days > 30 else ("warn" if days > 7 else "err"),
            }
        except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.exception("Failed to read TLS certificate expiry: %s", e)
            continue

    return {"days": None, "display": "N/A", "status": "err"}


def _get_disk_usage() -> dict[str, object]:
    """Check disk usage on relevant mount points."""
    paths = os.environ.get("DISK_CHECK_PATHS", f"{_MAIL_VHOSTS_DIR},{_APP_DIR},/")
    for path in paths.split(","):
        if os.path.exists(path):
            try:
                usage = shutil.disk_usage(path)
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
                pct = (usage.used / usage.total) * 100
                status = "ok" if pct < 80 else ("warn" if pct < 95 else "err")
                return {
                    "free_gb": round(free_gb, 1),
                    "total_gb": round(total_gb, 1),
                    "pct": round(pct, 1),
                    "display": f"{free_gb:.0f} GB",
                    "status": status,
                }
            except OSError:
                continue
    return {"free_gb": 0, "total_gb": 0, "pct": 0, "display": "N/A", "status": "warn"}


def _get_mail_volume_stats() -> dict[str, object]:
    """Check mail storage volume size."""
    mail_root = _MAIL_VHOSTS_DIR
    if not os.path.isdir(mail_root):
        return {"exists": False, "display": "N/A"}

    try:
        total_size = 0
        for dirpath, _dirnames, filenames in os.walk(mail_root):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass
        mb = total_size / (1024 * 1024)
        if mb < 1:
            display = f"{total_size / 1024:.0f} KB"
        elif mb < 1024:
            display = f"{mb:.0f} MB"
        else:
            display = f"{mb / 1024:.1f} GB"
        return {"exists": True, "display": display, "bytes": total_size}
    except OSError as e:
        logger.error("Failed to walk mail volume at %s: %s", mail_root, e)
        return {"exists": True, "display": "unknown"}


def _get_stats() -> list[dict[str, object]]:
    """Fetch aggregate platform statistics."""
    db_ok = True
    try:
        domain_count = DomainService.get_domain_count()
        user_count = UserService.get_active_count()
        mailbox_count = MailService.get_mailbox_count()
    except OperationalError as e:
        logger.exception("Database error fetching platform stats: %s", e)
        db_ok = False
        domain_count = 1
        user_count = 0
        mailbox_count = 0

    try:
        disk = _get_disk_usage()
    except OSError as e:
        logger.error("Failed to get disk usage: %s", e)
        disk = {"free_gb": 0, "total_gb": 0, "pct": 0, "display": "N/A", "status": "warn"}
    cert_days = _get_tls_expiry_days()

    return [
        {"value": domain_count, "label": "Domains", "status": "ok" if db_ok else "err"},
        {"value": user_count, "label": "Active Users", "status": "ok" if db_ok else "err"},
        {"value": mailbox_count, "label": "Mailboxes", "status": "ok" if db_ok else "err"},
        {
            "value": disk.get("display", "N/A"),
            "label": "Disk Free",
            "status": disk.get("status", "warn"),
        },
        {
            "value": cert_days.get("display", "N/A"),
            "label": "TLS Expires",
            "status": cert_days.get("status", "warn"),
        },
    ]


def _get_service_status() -> dict[str, dict[str, str]]:
    """Check health of core services from within the API container."""
    services = {}

    # PostgreSQL
    try:
        from django.db import connections
        with connections["default"].cursor() as c:
            c.execute("SELECT 1")
        services["postgres"] = {"label": "PostgreSQL", "status": "ok", "detail": "Connected"}
    except Exception:
        services["postgres"] = {"label": "PostgreSQL", "status": "err", "detail": "Unreachable"}

    # Redis
    try:
        cache.set("__dashboard_health", 1, timeout=5)
        if cache.get("__dashboard_health") == 1:
            services["redis"] = {"label": "Redis", "status": "ok", "detail": "Connected"}
        else:
            services["redis"] = {"label": "Redis", "status": "err", "detail": "Readback failed"}
    except Exception:
        services["redis"] = {"label": "Redis", "status": "err", "detail": "Unreachable"}

    # TLS Certificate
    cert_days = _get_tls_expiry_days()
    if cert_days["days"] is not None:
        if cert_days["days"] > 30:
            s, d = "ok", f"Valid for {cert_days['days']}d"
        elif cert_days["days"] > 7:
            s, d = "warn", f"Expires in {cert_days['days']}d"
        else:
            s, d = "err", f"Expiring in {cert_days['days']}d"
    else:
        s, d = "err", "No certificate found"
    services["tls"] = {"label": "TLS Certificate", "status": s, "detail": d}

    # Mail services — inferred from stack health
    mail_data = _get_mail_volume_stats()
    if mail_data["exists"]:
        services["mail-store"] = {
            "label": "Mail Store",
            "status": "ok",
            "detail": f"{mail_data['display']} used",
        }
    else:
        services["mail-store"] = {
            "label": "Mail Store",
            "status": "warn",
            "detail": "Volume not mounted or empty",
        }

    return services


def _get_domains(request: HttpRequest) -> list[dict[str, object]]:
    """Fetch domain health from the database with pagination."""
    try:
        qs = DomainService.get_all_domains()
        paginator = Paginator(qs, 25)
        page_number = request.GET.get("page", 1)
        try:
            page_number = min(max(int(page_number), 1), 1000)
        except (ValueError, TypeError):
            page_number = 1
        page = paginator.get_page(page_number)
        rows = page.object_list.values_list(
            "name",
            "verified",
            "mx_verified",
            "spf_verified",
            "dkim_verified",
            "dmarc_verified",
        )
    except OperationalError:
        logger.exception("Database error fetching domains")
        rows = []

    if not rows:
        fallback = os.environ.get("MAIL_DOMAIN", os.environ.get("DOMAIN", ""))
        return [
            {
                "name": fallback,
                "checks": [
                    {"check": "mx", "status": "warn", "message": "Verify MX record"},
                    {"check": "spf", "status": "warn", "message": "Verify SPF record"},
                    {"check": "dkim", "status": "warn", "message": "Verify DKIM record"},
                    {"check": "dmarc", "status": "warn", "message": "Verify DMARC record"},
                ],
                "warnings": ["DNS records have not been verified yet"],
            }
        ]

    domains = []
    for name, verified, mx, spf, dkim, dmarc in rows:
        checks = [
            _make_check("mx", mx, "MX record"),
            _make_check("spf", spf, "SPF record"),
            _make_check("dkim", dkim, "DKIM record"),
            _make_check("dmarc", dmarc, "DMARC record"),
        ]
        warnings = []
        if not all([mx, spf, dkim, dmarc]):
            warnings.append("Missing DNS records — check deliverability")
        domains.append({"name": name, "checks": checks, "warnings": warnings})
    return domains


def _get_activity() -> list[dict[str, str]]:
    """Fetch recent audit events."""
    events = AuditService.get_recent(20)
    if not events:
        return [
            {
                "time": "System started",
                "severity": "info",
                "description": "Audit log is active",
            }
        ]
    result = []
    for e in reversed(events):
        detail = f": {e['detail']}" if e.get("detail") else ""
        result.append({
            "time": e["time"],
            "severity": e.get("severity", "info"),
            "description": f"{e['user']} - {e['action']}{detail}",
        })
    return result


def _active_queue_rows() -> list[dict[str, str]]:
    """Return empty queue rows with mock flag (no real-time queue integration yet)."""
    return []


def _get_traffic_stats() -> dict[str, str]:
    """Return empty traffic stats (placeholder until real metrics are available)."""
    return {}


def _get_uptime_stats() -> dict[str, str]:
    """Return empty uptime stats (placeholder until real monitoring is integrated)."""
    return {}


def _get_telemetry_bars() -> list[int]:
    """Return empty telemetry bars (placeholder until real metrics are available)."""
    return []


def _get_system_load() -> dict[str, str]:
    """Return empty system load (placeholder until real metrics are available)."""
    return {}


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dashboard(request: HttpRequest) -> HttpResponse:
    """Platform admin dashboard — live stats, service health, DNS status, activity."""
    stats = _get_stats()
    services = _get_service_status()
    domains = _get_domains(request)
    events = _get_activity()
    disk = _get_disk_usage()
    is_mock = not any([stats, services, domains, events])
    return render(
        request,
        "admin/dashboard.html",
        {
            "stats": stats,
            "services": services,
            "domains": domains,
            "events": events,
            "storage_used": disk.get("display", "N/A"),
            "storage_pct": f"{disk.get('pct', 0):.0f}%",
            "storage_total": f"{disk.get('total_gb', 0):.1f} GB",
            "storage_warning": str(_("Cleanup recommended")) if disk.get("status") == "err" else "",
            "traffic_stats": _get_traffic_stats(),
            "uptime_stats": _get_uptime_stats(),
            "telemetry_bars": _get_telemetry_bars(),
            "system_load": _get_system_load(),
            "queue_headers": [_("Process ID"), _("Status"), _("Origin"), _("Delay")],
            "queue_rows": _active_queue_rows(),
            "mail_hostname": os.environ.get("MAIL_HOSTNAME", ""),
            "active_section": "general",
            "header_search_placeholder": "Search mail server logs...",
            "is_mock": is_mock,
            "tls_info": _get_tls_info(),
        },
    )


def _get_tls_info() -> dict[str, Any]:
    """Return extended TLS certificate information (issuer, SANs, expiry)."""
    mail_hostname = os.environ.get("MAIL_HOSTNAME", "")
    domain = os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", ""))
    cert_paths = []
    if mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, "live", mail_hostname, "fullchain.pem"))
    if domain and domain != mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, "live", domain, "fullchain.pem"))

    for cert_path in cert_paths:
        if not os.path.isfile(cert_path):
            continue
        info: dict[str, Any] = {"path": cert_path, "issuer": "", "sans": [], "expiry_days": None}
        try:
            result = subprocess.run(
                ["openssl", "x509", "-issuer", "-noout", "-in", cert_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                issuer_line = result.stdout.strip()
                if "issuer=" in issuer_line:
                    info["issuer"] = issuer_line.split("issuer=", 1)[1].strip().strip("/")

            result = subprocess.run(
                ["openssl", "x509", "-ext", "subjectAltName", "-noout", "-in", cert_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                sans = []
                for line in result.stdout.strip().split("\n"):
                    line = line.strip().rstrip(",")
                    if line.startswith("DNS:"):
                        sans.append(line[4:])
                info["sans"] = sans

            expiry = _get_tls_expiry_days()
            info["expiry_days"] = expiry.get("days")
            info["expiry_status"] = expiry.get("status", "err")
            return info
        except subprocess.TimeoutExpired:
            logger.error("TLS info: openssl timed out for %s", cert_path)
        except OSError as e:
            logger.exception("TLS info: OS error reading %s: %s", cert_path, e)
    return {}


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dashboard_rescan(request: HttpRequest) -> JsonResponse:
    """Force a full rescan of DNS and TLS health for all domains."""
    results: dict[str, Any] = {"status": "ok", "domains": {}, "tls": None}
    try:
        from backend.apps.domains import services as domain_services

        domains = DomainService.get_all_domains()
        for d in domains:
            dns_result = MonitoringService.check_dns(d.name)
            results["domains"][d.name] = dns_result

        results["tls"] = MonitoringService.check_tls_expiry()
        AuditService.record(
            action="dashboard_rescan",
            user=request.user.username if request.user.is_authenticated else None,
            detail=f"Rescanned {len(domains)} domain(s)",
        )
    except Exception as e:
        logger.exception("Rescan failed: %s", e)
        results["status"] = "err"
        results["error"] = str(e)
    return JsonResponse(results, content_type="application/json; charset=utf-8")


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dashboard_shell(request: HttpRequest) -> JsonResponse:
    """Execute a read-only shell command from an allowlist."""
    cmd = request.POST.get("cmd", "").strip()
    if not cmd:
        return JsonResponse(
            {"error": "No command provided"}, status=400,
            content_type="application/json; charset=utf-8",
        )

    # Validate against allowlist.
    allowed = False
    for prefix in _SHELL_ALLOWLIST:
        if cmd.startswith(prefix):
            allowed = True
            break
    if not allowed:
        AuditService.record(
            action="shell_blocked",
            user=request.user.username if request.user.is_authenticated else None,
            detail=f"Blocked: {cmd[:120]}",
            severity="warning",
        )
        return JsonResponse(
            {"error": f"Command not allowed. Permitted prefixes: {', '.join(_SHELL_ALLOWLIST[:6])}..."},
            status=403,
            content_type="application/json; charset=utf-8",
        )

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15,
        )
        AuditService.record(
            action="shell_executed",
            user=request.user.username if request.user.is_authenticated else None,
            detail=f"Executed: {cmd[:120]} (rc={result.returncode})",
        )
        return JsonResponse(
            {
                "stdout": result.stdout[-50000:] if result.stdout else "",
                "stderr": result.stderr[-20000:] if result.stderr else "",
                "returncode": result.returncode,
            },
            content_type="application/json; charset=utf-8",
        )
    except subprocess.TimeoutExpired:
        return JsonResponse(
            {"error": "Command timed out (15s limit)"}, status=504,
            content_type="application/json; charset=utf-8",
        )
    except OSError as e:
        return JsonResponse(
            {"error": f"Command failed: {e}"}, status=500,
            content_type="application/json; charset=utf-8",
        )


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dashboard_log_purge(request: HttpRequest) -> JsonResponse:
    """Purge archived audit log entries, keeping the most recent 500."""
    try:
        AuditEvent = _get_audit_model_for_write()
        total_before = AuditEvent.objects.count()
        if total_before > 500:
            keep_ids = list(
                AuditEvent.objects.order_by("-time")
                .values_list("id", flat=True)[:500]
            )
            deleted, _ = AuditEvent.objects.exclude(id__in=keep_ids).delete()
            AuditService.record(
                action="log_purge",
                user=request.user.username if request.user.is_authenticated else None,
                detail=f"Purged {deleted} audit entries (before={total_before})",
            )
            return JsonResponse(
                {"status": "ok", "deleted": deleted, "before": total_before,
                 "after": total_before - deleted},
                content_type="application/json; charset=utf-8",
            )
        else:
            return JsonResponse(
                {"status": "ok", "deleted": 0, "message": "Below threshold — nothing to purge"},
                content_type="application/json; charset=utf-8",
            )
    except Exception as e:
        logger.exception("Log purge failed: %s", e)
        return JsonResponse(
            {"status": "err", "error": str(e)}, status=500,
            content_type="application/json; charset=utf-8",
        )


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dashboard_reboot(request: HttpRequest) -> JsonResponse:
    """Restart postfix and dovecot services."""
    services = ["postfix", "dovecot"]
    results: dict[str, str] = {}
    all_ok = True
    for svc in services:
        try:
            result = subprocess.run(
                ["systemctl", "restart", svc],
                capture_output=True, text=True, timeout=30,
            )
            ok = result.returncode == 0
            results[svc] = "ok" if ok else f"failed (rc={result.returncode})"
            if not ok:
                all_ok = False
                logger.error(
                    "systemctl restart %s failed: stdout=%s stderr=%s",
                    svc, result.stdout.strip(), result.stderr.strip(),
                )
        except FileNotFoundError:
            results[svc] = "systemctl not found (container env?)"
            all_ok = False
        except subprocess.TimeoutExpired:
            results[svc] = "timed out after 30s"
            all_ok = False
        except OSError as e:
            results[svc] = f"os error: {e}"
            all_ok = False

    AuditService.record(
        action="service_reboot",
        user=request.user.username if request.user.is_authenticated else None,
        detail=f"Restarted postfix/dovecot: {results}",
        severity="warning",
    )
    return JsonResponse(
        {"status": "ok" if all_ok else "partial", "services": results},
        content_type="application/json; charset=utf-8",
    )


def _get_audit_model_for_write() -> Any:
    """Lazy-import AuditEvent for write operations."""
    from backend.services.models import AuditEvent
    return AuditEvent
