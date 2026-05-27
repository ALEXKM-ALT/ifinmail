"""Admin dashboard views for ifinmail."""
import logging
import os
import re
import shutil
from datetime import datetime, timezone

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.utils import IntegrityError, OperationalError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from backend.apps.accounts.models import MailUser
from backend.apps.domains.models import Domain
from backend.apps.mail.models import Mailbox
from backend.services.audit import AuditService

logger = logging.getLogger("backend")

_IPIFY_URL = "https://api.ipify.org"
_LETSENCRYPT_DIR = os.environ.get("LETSENCRYPT_DIR", "/etc/letsencrypt")
_MAIL_VHOSTS_DIR = os.environ.get("MAIL_VHOSTS_DIR", "/var/mail/vhosts")
_APP_DIR = os.environ.get("APP_DIR", "/app")

# Domain name validation regex (RFC 952 / RFC 1123)
_DOMAIN_RE = re.compile(
    r"^(?!-)[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.?$"
)
_ALLOWED_HOST_NAMES = tuple(
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
)


def _validate_domain(name: str) -> str:
    """Validate and normalize a domain name. Returns empty string if invalid."""
    if not name or len(name) > 253:
        return ""
    # Strip protocol prefix if user accidentally includes it
    name = re.sub(r"^https?://", "", name.strip().lower())
    # Strip trailing dot (FQDN notation)
    name = name.rstrip(".")
    if _DOMAIN_RE.match(name):
        return name
    return ""


def _is_staff(user):
    """Check staff status with database revalidation."""
    if not user.is_authenticated:
        return False
    # Re-fetch from DB to catch privilege downgrades mid-session
    try:
        user.refresh_from_db(fields=["is_staff", "is_superuser", "is_active"])
    except Exception:
        return False
    if not user.is_active:
        return False
    return user.is_staff or user.is_superuser


def login_view(request):
    """Admin login view."""
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        # Check for Axes lockout before attempting auth
        try:
            from axes.helpers import get_lockout_message, is_already_locked
            from axes.conf import settings as axes_settings

            if callable(axes_settings.AXES_LOCKOUT_CALLABLE):
                credentials = {"username": email, "ip_address": request.META.get("REMOTE_ADDR", "")}
                if axes_settings.AXES_LOCKOUT_CALLABLE(request, credentials):
                    error = get_lockout_message() or "Account locked. Try again later."
                    AuditService.record(
                        "login_blocked",
                        user=email,
                        detail="Account locked by Axes",
                        severity="warn",
                    )
                    return render(request, "admin/login.html", {"error": error})
            # Backward compat - Axes <6
            elif is_already_locked(request):
                error = get_lockout_message(request) or "Account locked. Try again later."
                AuditService.record(
                    "login_blocked",
                    user=email,
                    detail="Account locked by Axes",
                    severity="warn",
                )
                return render(request, "admin/login.html", {"error": error})
        except ImportError:
            pass

        user = authenticate(request, username=email, password=password)
        if user is not None:
            # EC-01: Cycle session key to prevent session fixation
            request.session.cycle_key()
            login(request, user)

            AuditService.record(
                "login_success",
                user=user.email,
                detail=f"IP: {request.META.get('REMOTE_ADDR', 'unknown')}",
                severity="info",
            )

            next_url = request.GET.get("next", "")
            # EC-05: Validate redirect target to prevent open redirect attacks
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts=_ALLOWED_HOST_NAMES or None,
            ):
                return redirect(next_url)
            return redirect("accounts:dashboard")

        # EC-13: Audit failed login attempt
        AuditService.record(
            "login_failed",
            user=email,
            detail=f"IP: {request.META.get('REMOTE_ADDR', 'unknown')}",
            severity="warn",
        )
        error = "Invalid email or password."
    return render(request, "admin/login.html", {"error": error})


def logout_view(request):
    """Admin logout view — fully flush session to prevent reuse across tabs."""
    AuditService.record(
        "logout",
        user=getattr(request.user, "email", "unknown"),
        detail="User logged out",
        severity="info",
    )
    # EC-07: Full session flush for all tabs
    request.session.flush()
    logout(request)
    return redirect("accounts:login")


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dashboard(request):
    """Platform admin dashboard — live stats, service health, DNS status, activity."""
    stats = _get_stats()
    services = _get_service_status()
    domains = _get_domains(request)
    events = _get_activity()
    return render(
        request,
        "admin/dashboard.html",
        {
            "stats": stats,
            "services": services,
            "domains": domains,
            "events": events,
            "mail_hostname": os.environ.get("MAIL_HOSTNAME", ""),
        },
    )


def _get_stats():
    """Fetch aggregate platform statistics."""
    db_ok = True
    try:
        with transaction.atomic():
            domain_count = Domain.objects.count()
            user_count = MailUser.objects.filter(is_active=True).count()
            mailbox_count = Mailbox.objects.count()
    except OperationalError:
        logger.exception("Database error fetching platform stats")
        db_ok = False
        domain_count = 1
        user_count = 0
        mailbox_count = 0

    disk = _get_disk_usage()
    cert_days = _get_tls_expiry_days()

    return [
        {"value": domain_count, "label": "Domains", "status": "ok" if db_ok else "err"},
        {"value": user_count, "label": "Active Users", "status": "ok" if db_ok else "err"},
        {"value": mailbox_count, "label": "Mailboxes", "status": "ok" if db_ok else "err"},
        {"value": disk.get("display", "N/A"), "label": "Disk Free", "status": disk.get("status", "warn")},
        {"value": cert_days.get("display", "N/A"), "label": "TLS Expires", "status": cert_days.get("status", "warn")},
    ]


def _get_service_status():
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
        services["mail-store"] = {"label": "Mail Store", "status": "ok", "detail": f"{mail_data['display']} used"}
    else:
        services["mail-store"] = {"label": "Mail Store", "status": "warn", "detail": "Volume not mounted or empty"}

    return services


def _get_tls_expiry_days():
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
        except Exception:
            logger.exception("Failed to read TLS certificate expiry")
            continue

    return {"days": None, "display": "N/A", "status": "err"}


def _get_disk_usage():
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


def _get_mail_volume_stats():
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
    except OSError:
        return {"exists": True, "display": "unknown"}


def _get_domains(request):
    """Fetch domain health from the database with pagination."""
    try:
        qs = Domain.objects.order_by("name")
        paginator = Paginator(qs, 25)
        page_number = request.GET.get("page", 1)
        # EC-31: Clamp page number to prevent excessive queries
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


def _make_check(code, status_bool, label):
    if status_bool:
        return {"check": code, "status": "pass", "message": f"{label} verified"}
    return {"check": code, "status": "warn", "message": f"Verify {label}"}


def _get_activity():
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
        result.append({
            "time": e["time"],
            "severity": e.get("severity", "info"),
            "description": f"{e['user']} — {e['action']}{': ' + e['detail'] if e.get('detail') else ''}",
        })
    return result


# ─── Setup Complete Flag (DB-backed, not session-only) ──────────


def _setup_is_complete() -> bool:
    """Check if setup has been completed (DB-backed flag, EC-11)."""
    try:
        return bool(MailUser.objects.filter(is_staff=True, is_active=True).exists())
    except Exception:
        return False


# ─── Setup Wizard Views ──────────────────────────────────────────────


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def setup_wizard(request):
    """Redirect to the current setup wizard step."""
    if _setup_is_complete():
        return redirect("accounts:dashboard")
    return redirect("accounts:setup_step", step="welcome")


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def setup_step(request, step):
    """Render a setup wizard step."""
    if _setup_is_complete():
        return redirect("accounts:dashboard")

    domain = request.session.get("setup_domain") or os.environ.get("DOMAIN", "")
    dns_provider = request.session.get("setup_dns_provider", "")

    context = {
        "step": step,
        "domain": domain,
        "dns_provider": dns_provider,
        "server_ip": _setup_server_ip(),
    }

    if step == "welcome":
        template = "setup/welcome.html"
    elif step == "dns":
        template = "setup/dns_provider.html"
    elif step == "dns-auto":
        template = "setup/dns_auto.html"
    elif step == "dns-manual":
        template = "setup/dns_manual.html"
    elif step == "account":
        template = "setup/create_account.html"
    elif step == "done":
        template = "setup/done.html"
    else:
        return redirect("accounts:setup_step", step="welcome")

    return render(request, template, context)


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def setup_advance(request):
    """POST handler that advances the wizard one step."""
    if request.method != "POST":
        return redirect("accounts:setup_step", step="welcome")

    # Block re-execution if setup is DB-complete
    if _setup_is_complete():
        return redirect("accounts:dashboard")

    current = request.POST.get("current_step", "welcome")
    skip = request.POST.get("skip", "") == "1"

    if current == "welcome":
        domain = request.POST.get("domain", "").strip()
        if domain and not skip:
            # EC-42: Validate domain name format before accepting
            valid_domain = _validate_domain(domain)
            if not valid_domain:
                AuditService.record(
                    "setup_invalid_domain",
                    user=request.user.email,
                    detail=f"Rejected invalid domain: {domain}",
                    severity="warn",
                )
                return redirect("accounts:setup_step", step="welcome")
            request.session["setup_domain"] = valid_domain
            # EC-21: Wrap get_or_create in atomic transaction to prevent race conditions
            try:
                with transaction.atomic():
                    Domain.objects.get_or_create(name=valid_domain)
            except IntegrityError:
                logger.warning("Race condition on domain get_or_create for %s", valid_domain)
            except Exception:
                pass
        next_step = "dns"

    elif current == "dns":
        if not skip:
            provider = request.POST.get("provider", "")
            request.session["setup_dns_provider"] = provider
            # EC-12: Do NOT store API tokens in session — they go to DB via dns_configure view
            next_step = "dns-auto" if provider else "account"
        else:
            next_step = "account"

    elif current == "dns-auto":
        next_step = "account"
    elif current == "dns-manual":
        next_step = "account"

    elif current == "account":
        if not skip:
            email = request.POST.get("email", "").strip()
            password = request.POST.get("password", "")
            if email and password:
                _create_first_account(email, password, request)
        next_step = "done"

    elif current == "done":
        response = redirect("accounts:dashboard")
        return response

    else:
        next_step = "welcome"

    return redirect("accounts:setup_step", step=next_step)


def _setup_server_ip() -> str:
    ip_check_url = os.environ.get("IP_CHECK_URL", _IPIFY_URL)
    try:
        import requests as req
        resp = req.get(ip_check_url, timeout=5)
        if resp.status_code == 200:
            ip = resp.text.strip()
            # EC-43: Detect and warn on private IP addresses
            if ip.startswith(("10.", "172.", "192.168.", "127.")):
                logger.warning("Detected private IP %s — DNS records may be wrong", ip)
            return ip
    except Exception:
        pass
    try:
        import socket
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "0.0.0.0"


def _create_first_account(email: str, password: str, request):
    """Create the first mailbox and user account during setup."""
    try:
        local_part, _, domain_name = email.partition("@")
        if not domain_name:
            return

        # EC-21: Wrap get_or_create in atomic transaction to prevent race conditions
        with transaction.atomic():
            domain, _ = Domain.objects.get_or_create(name=domain_name)
            Mailbox.objects.get_or_create(domain=domain, local_part=local_part)

            if not MailUser.objects.filter(username=email).exists():
                MailUser.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    is_staff=True,
                )

        AuditService.record(
            "account_created",
            user=request.user.email,
            detail=email,
            severity="info",
        )
    except IntegrityError:
        # EC-21: Handle duplicate key from concurrent get_or_create races
        logger.warning(
            "IntegrityError during account creation for %s — likely race condition", email
        )
    except Exception as e:
        logger.exception("Failed to create first account during setup: %s", e)
