"""Setup wizard views."""
import logging
import os
import re

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.utils import IntegrityError, OperationalError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from backend.apps.accounts.services import UserService
from backend.apps.domains.services import DomainService
from backend.apps.mail.services import MailService
from backend.services.audit import AuditService

from backend.apps.dns.services import DNSService
from ._constants import _DOMAIN_RE, _IPIFY_URL
from .auth import _is_staff

logger = logging.getLogger("backend")


def _validate_domain(name: str) -> str:
    """Validate and normalize a domain name. Returns empty string if invalid."""
    if not name or len(name) > 253:
        return ""
    name = re.sub(r"^https?://", "", name.strip().lower())
    name = name.rstrip(".")
    if _DOMAIN_RE.match(name):
        return name
    return ""


def _setup_is_complete() -> bool:
    """Check if setup has been completed (DB-backed flag, EC-11)."""
    try:
        return UserService.has_staff_users()
    except OperationalError as e:
        logger.warning("Database not ready for setup check: %s", e)
        return False


def _setup_server_ip() -> str:
    ip_check_url = os.environ.get("IP_CHECK_URL", _IPIFY_URL)
    try:
        import requests as req
        resp = req.get(ip_check_url, timeout=5)
        if resp.status_code == 200:
            ip = resp.text.strip()
            if ip.startswith(("10.", "172.", "192.168.", "127.")):
                logger.warning("Detected private IP %s — DNS records may be wrong", ip)
            return ip
    except Exception as e:
        logger.warning("Failed to detect server IP via %s: %s", ip_check_url, e)
    try:
        import socket
        return socket.gethostbyname(socket.gethostname())
    except Exception as e:
        logger.warning("Failed to resolve hostname: %s", e)
        return "0.0.0.0"


def _create_first_account(email: str, password: str, request: HttpRequest) -> None:
    """Create the first mailbox and user account during setup."""
    try:
        local_part, _, domain_name = email.partition("@")
        if not domain_name:
            return

        with transaction.atomic():
            domain, _ = DomainService.get_or_create_domain(name=domain_name)
            MailService.get_or_create_mailbox(domain=domain, local_part=local_part)

            if not UserService.get_user_by_email(email):
                UserService.create_user(email=email, password=password, is_active=True, is_staff=True)

        AuditService.record(
            "account_created",
            user=request.user.email,
            detail=email,
            severity="info",
        )
    except IntegrityError:
        logger.warning(
            "IntegrityError during account creation for %s — likely race condition", email
        )
    except Exception as e:
        logger.exception("Failed to create first account during setup: %s", e)


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def setup_wizard(request: HttpRequest) -> HttpResponse:
    """Redirect to the current setup wizard step."""
    if _setup_is_complete():
        return redirect("accounts:dashboard")
    return redirect("accounts:setup_step", step="welcome")


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def setup_step(request: HttpRequest, step: str) -> HttpResponse:
    """Render a setup wizard step."""
    if _setup_is_complete():
        return redirect("accounts:dashboard")

    domain = request.session.get("setup_domain") or os.environ.get("DOMAIN", "")
    dns_provider = request.session.get("setup_dns_provider", "")
    server_ip = _setup_server_ip()

    context = {
        "step": step,
        "domain": domain,
        "dns_provider": dns_provider,
        "server_ip": server_ip,
    }

    if step == "welcome":
        template = "setup/welcome.html"
    elif step == "dns":
        template = "setup/dns_provider.html"
    elif step == "dns-auto":
        template = "setup/dns_auto.html"
        if not domain:
            return redirect("accounts:setup_step", step="dns")
    elif step == "dns-manual":
        template = "setup/dns_manual.html"
        if not domain:
            return redirect("accounts:setup_step", step="dns")
        if domain and server_ip and server_ip != "0.0.0.0":
            raw_records = DNSService.build_records(domain, server_ip)
            dns_records = []
            for rec in raw_records:
                display_name = rec.name if rec.name != "@" else ""
                if display_name and not display_name.startswith("_"):
                    display_name = f"{rec.name}.{domain}"
                elif display_name:
                    display_name = f"{rec.name}.{domain}"
                elif rec.type == "A":
                    display_name = domain  # root A record shows bare domain
                else:
                    display_name = domain
                value = rec.value
                if rec.type == "MX":
                    value = f"{rec.priority} {rec.value}"
                elif rec.type == "TXT":
                    value = f'"{rec.value}"'
                dns_records.append({
                    "type": rec.type,
                    "name": display_name,
                    "value": value,
                })
            context["dns_records"] = dns_records
    elif step == "account":
        template = "setup/create_account.html"
    elif step == "done":
        template = "setup/done.html"
    else:
        return redirect("accounts:setup_step", step="welcome")

    return render(request, template, context)


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def setup_advance(request: HttpRequest) -> HttpResponse:
    """POST handler that advances the wizard one step."""
    if request.method != "POST":
        return redirect("accounts:setup_step", step="welcome")

    if _setup_is_complete():
        return redirect("accounts:dashboard")

    current = request.POST.get("current_step", "welcome")
    skip = request.POST.get("skip", "") == "1"

    if current == "welcome":
        domain = request.POST.get("domain", "").strip()
        if domain and not skip:
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
            try:
                DomainService.get_or_create_domain(name=valid_domain)
            except IntegrityError:
                logger.warning("Race condition on domain get_or_create for %s", valid_domain)
            except Exception as e:
                logger.exception("Failed to create domain %s during setup: %s", valid_domain, e)
        next_step = "dns"

    elif current == "dns":
        if not skip:
            provider = request.POST.get("provider", "")
            request.session["setup_dns_provider"] = provider
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
        # Clear session state on completion
        request.session.pop("setup_domain", None)
        request.session.pop("setup_dns_provider", None)
        response = redirect("accounts:dashboard")
        return response

    else:
        next_step = "welcome"

    return redirect("accounts:setup_step", step=next_step)
