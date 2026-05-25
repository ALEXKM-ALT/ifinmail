"""DNS configuration views."""
import logging
import os
import socket
from datetime import datetime, timezone

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from backend.apps.dns.models import DNSProviderConfig
from backend.apps.dns.providers.base import DNSRecord
from backend.apps.dns.providers.cloudflare import CloudflareProvider
from backend.apps.dns.providers.digitalocean import DigitalOceanProvider
from backend.apps.dns.providers.porkbun import PorkbunProvider
from backend.services.monitoring import MonitoringService

logger = logging.getLogger("backend")

PROVIDER_MAP = {
    "cloudflare": (CloudflareProvider, {"api_token"}, "API Token"),
    "porkbun": (PorkbunProvider, {"api_key", "secret_key"}, "API Key + Secret Key"),
    "digitalocean": (DigitalOceanProvider, {"api_token"}, "API Token"),
}

_IPIFY_URL = "https://api.ipify.org"
_DEFAULT_DNS_TTL = int(os.environ.get("DNS_TTL", "3600"))
_DKIM_KEY_DIR = os.environ.get("DKIM_KEY_DIR", "/etc/dkim")
_LETSENCRYPT_DIR = os.environ.get("LETSENCRYPT_DIR", "/etc/letsencrypt")


def _is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _build_records(domain: str, server_ip: str) -> list[DNSRecord]:
    mail_hostname = os.environ.get("MAIL_HOSTNAME", f"mail.{domain}")
    dkim_selector = os.environ.get("DKIM_SELECTOR", "default")
    ttl = _DEFAULT_DNS_TTL

    dkim_value = ""
    dkim_pub_path = os.path.join(_DKIM_KEY_DIR, f"{dkim_selector}.{domain}.pub")
    if os.path.isfile(dkim_pub_path):
        try:
            with open(dkim_pub_path) as f:
                dkim_value = "".join(line.strip() for line in f if not line.startswith("-"))
        except OSError:
            pass

    mta_sts_id = os.environ.get("MTA_STS_ID", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    return [
        DNSRecord(type="A", name="@", value=server_ip, ttl=ttl),
        DNSRecord(type="A", name="mail", value=server_ip, ttl=ttl),
        DNSRecord(type="A", name="mta-sts", value=server_ip, ttl=ttl),
        DNSRecord(type="MX", name="@", value=mail_hostname, priority=10, ttl=ttl),
        DNSRecord(type="TXT", name="@", value="v=spf1 mx -all", ttl=ttl),
        DNSRecord(type="TXT", name="_dmarc", value=f"v=DMARC1; p=quarantine; rua=mailto:postmaster@{domain}", ttl=ttl),
        DNSRecord(type="TXT", name="_mta-sts", value=f"v=STSv1; id={mta_sts_id}", ttl=ttl),
        DNSRecord(
            type="TXT", name=f"{dkim_selector}._domainkey",
            value=f"v=DKIM1; k=rsa; p={dkim_value}" if dkim_value else "v=DKIM1; k=rsa; p=<add-dkim-key>",
            ttl=ttl,
        ),
    ]


def _get_server_ip() -> str:
    """Auto-detect the server's public IPv4 address."""
    ip_check_url = os.environ.get("IP_CHECK_URL", _IPIFY_URL)
    try:
        import requests as req
        resp = req.get(ip_check_url, timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception:
        logger.exception("Failed to detect public IP via %s", ip_check_url)
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "0.0.0.0"


def _get_provider(provider_name: str):
    config = DNSProviderConfig.objects.filter(provider=provider_name).first()
    if not config:
        return None
    cls, _, _ = PROVIDER_MAP[provider_name]
    return cls(**config.credentials)


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_config_page(request):
    """Render the DNS configuration page."""
    domain = os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", ""))
    server_ip = _get_server_ip()
    providers = [
        {"id": pid, "name": cls.provider_name if hasattr(cls, 'provider_name') else pid.capitalize(), "fields": fields, "label": label}
        for pid, (cls, fields, label) in PROVIDER_MAP.items()
    ]

    # Check if any provider is already configured
    saved = DNSProviderConfig.objects.first()
    saved_provider = saved.provider if saved else None

    context = {
        "domain": domain,
        "server_ip": server_ip,
        "providers": providers,
        "saved_provider": saved_provider,
        "dns_status": _get_dns_status(domain),
    }
    return render(request, "admin/dns_config.html", context)


def _get_dns_status(domain: str) -> dict:
    """Check DNS records via the monitoring service."""
    try:
        return MonitoringService.check_dns(domain)
    except Exception:
        return {}


@require_POST
@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_configure(request):
    """POST endpoint: configure DNS records via the selected provider."""
    provider_name = request.POST.get("provider", "").lower()
    domain = request.POST.get("domain", os.environ.get("DOMAIN", ""))

    if provider_name not in PROVIDER_MAP:
        return JsonResponse({"success": False, "message": f"Unknown provider: {provider_name}"}, status=400)

    cls, fields, _ = PROVIDER_MAP[provider_name]
    creds = {f: request.POST.get(f, "").strip() for f in fields}
    if not all(creds.values()):
        missing = [f for f, v in creds.items() if not v]
        return JsonResponse({"success": False, "message": f"Missing credentials: {', '.join(missing)}"}, status=400)

    # Save credentials (overwrite existing for this provider)
    DNSProviderConfig.objects.update_or_create(
        provider=provider_name,
        defaults={"credentials": creds},
    )

    # Build records and configure
    server_ip = _get_server_ip()
    records = _build_records(domain, server_ip)

    try:
        provider = cls(**creds)
        result = provider.configure_domain(domain, records)
        return JsonResponse({
            "success": result.success,
            "message": result.message,
            "records_created": result.records_created,
            "records_failed": result.records_failed,
        })
    except Exception as e:
        logger.exception("DNS configuration failed for %s via %s", domain, provider_name)
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_status(request):
    """GET endpoint: return current DNS record verification status."""
    domain = request.GET.get("domain", os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", "")))
    try:
        status = MonitoringService.check_dns(domain)
        return JsonResponse({"domain": domain, "records": status})
    except Exception as e:
        return JsonResponse({"domain": domain, "error": str(e)}, status=500)
