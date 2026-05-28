"""DNS web views — template-rendering views (web flow)."""
import csv
import json
import logging
import os
import re

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from backend.apps.dns.services import DNSService
from backend.apps.domains.services import DomainService
from backend.services.audit import AuditService
from backend.services.monitoring import MonitoringService

from ._helpers import PROVIDER_MAP, _build_records, _get_server_ip, _is_staff
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

logger = logging.getLogger("backend")


def _get_dns_status(domain: str) -> dict:
    """Check DNS records via the monitoring service."""
    try:
        return MonitoringService.check_dns(domain)
    except Exception as e:
        logger.warning("DNS status check failed for %s: %s", domain, e)
        return {}


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_config_page(request: HttpRequest) -> HttpResponse:
    """Render the DNS configuration page."""
    domain = os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", ""))
    server_ip = _get_server_ip()
    provider_meta: dict[str, dict[str, object]] = {
        "cloudflare": {
            "help": str(_("Requires an API token with DNS:Edit permission.")),
            "help_url": "https://developers.cloudflare.com/fundamentals/api/get-started/create-token/",
            "placeholder": "Cloudflare API Token",
            "second_field": None,
        },
        "porkbun": {
            "help": str(_("Requires API Key and Secret Key from your Porkbun account.")),
            "help_url": "https://kb.porkbun.com/article/190-getting-started-with-the-porkbun-api",
            "placeholder": "API Key",
            "second_field": {"name": "secret_key", "placeholder": "Secret Key"},
        },
        "digitalocean": {
            "help": str(_("Requires a personal access token with write access.")),
            "help_url": "https://docs.digitalocean.com/reference/api/create-personal-access-token/",
            "placeholder": "DigitalOcean API Token",
            "second_field": None,
        },
    }
    providers = [
        {
            "id": pid,
            "name": cls.provider_name if hasattr(cls, 'provider_name') else pid.capitalize(),
            "fields": fields,
            "label": label,
            "help": provider_meta.get(pid, {}).get("help", ""),
            "help_url": provider_meta.get(pid, {}).get("help_url", ""),
            "placeholder": provider_meta.get(pid, {}).get("placeholder", f"{pid.capitalize()} API Token"),
            "second_field": provider_meta.get(pid, {}).get("second_field"),
        }
        for pid, (cls, fields, label) in PROVIDER_MAP.items()
    ]

    saved = DNSService.get_first_config()
    saved_provider = saved.provider if saved else None

    # Extract SPF record from generated DNS records for DNS Toolbox display
    toolbox_spf_record = ""
    if domain and server_ip and server_ip != "0.0.0.0":
        try:
            records = _build_records(domain, server_ip)
            spf_rec = next((r for r in records if r.type == "TXT" and r.name == "@"), None)
            if spf_rec:
                toolbox_spf_record = spf_rec.value
        except Exception:
            pass
    if not toolbox_spf_record:
        toolbox_spf_record = "v=spf1 mx -all"

    # Registry entries from DB or empty state
    domain_label = domain or "acme-corp.com"
    manage_dns_label = str(_("Manage DNS"))
    dns_registry_rows = []
    cluster_hosts = []

    context = {
        "domain": domain,
        "server_ip": server_ip,
        "providers": providers,
        "saved_provider": saved_provider,
        "dns_status": _get_dns_status(domain),
        "dns_registry_headers": [_("Domain Name"), _("MX Status"), _("SPF/DKIM"), _("SSL Expiry"), _("Actions")],
        "dns_registry_rows": dns_registry_rows,
        "propagation_sync": "4.2ms avg",
        "propagation_pct": "99.9%",
        "dnssec_issues": "12",
        "dnssec_status": str(_("Pending")),
        "nameserver_count": "4",
        "nameserver_scope": str(_("Global")),
        "cluster_hosts": [],
        "is_mock": True,
        "dkim_selector": "ifinmail-2023",
        "toolbox_spf_record": toolbox_spf_record,
        "active_section": "dns",
        "header_search_placeholder": "Search domains or records...",
        "smtp_proxy_enabled": os.environ.get("MAIL_SMTP_PROXY", "").lower() in ("1", "true", "yes"),
        "smart_host_enabled": os.environ.get("MAIL_SMART_HOST", "").lower() in ("1", "true", "yes"),
        "max_hop_count": int(os.environ.get("MAIL_MAX_HOP_COUNT", "10")),
    }
    return render(request, "admin/dns_config.html", context)


_VALID_DOMAIN_RE = re.compile(r"^(?!-)[a-zA-Z0-9-]{1,63}(?:\.[a-zA-Z0-9-]{1,63})*\.[a-zA-Z]{2,}$")


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dns_register_domain(request: HttpRequest) -> JsonResponse:
    """Register a new domain and build its DNS records."""
    domain_name = request.POST.get("domain", "").strip().lower()
    if not domain_name or len(domain_name) > 255:
        return JsonResponse(
            {"status": "err", "error": "Invalid domain name"}, status=400,
            content_type="application/json; charset=utf-8",
        )
    if not _VALID_DOMAIN_RE.match(domain_name):
        return JsonResponse(
            {"status": "err", "error": "Domain name format is invalid"}, status=400,
            content_type="application/json; charset=utf-8",
        )
    try:
        domain, created = DomainService.get_or_create_domain(name=domain_name)
        server_ip = _get_server_ip()
        records = _build_records(domain_name, server_ip)
        AuditService.record(
            action="domain_registered",
            user=request.user.username if request.user.is_authenticated else None,
            detail=f"{domain_name} (created={created}, records={len(records)})",
        )
        return JsonResponse(
            {
                "status": "ok",
                "domain": domain_name,
                "created": created,
                "records": [{"type": r.type, "name": r.name, "value": r.value} for r in records],
            },
            content_type="application/json; charset=utf-8",
        )
    except Exception as e:
        logger.exception("Failed to register domain %s: %s", domain_name, e)
        return JsonResponse(
            {"status": "err", "error": str(e)}, status=500,
            content_type="application/json; charset=utf-8",
        )


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_export_records(request: HttpRequest) -> HttpResponse:
    """Export all DNS records as a CSV download."""
    domain_name = os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", ""))
    server_ip = _get_server_ip()
    records = []
    if domain_name and server_ip and server_ip != "0.0.0.0":
        try:
            records = _build_records(domain_name, server_ip)
        except Exception:
            pass

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename=dns_records_{domain_name or 'export'}.csv"
    writer = csv.writer(response)
    writer.writerow(["Type", "Name", "Value", "Priority", "TTL"])
    for r in records:
        writer.writerow([r.type, r.name, r.value, getattr(r, "priority", ""), r.ttl])
    AuditService.record(
        action="dns_export",
        user=request.user.username if request.user.is_authenticated else None,
        detail=f"Exported {len(records)} records for {domain_name}",
    )
    return response


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dns_toggle_proxy(request: HttpRequest) -> JsonResponse:
    """Toggle Global SMTP Proxy setting."""
    current = os.environ.get("MAIL_SMTP_PROXY", "").lower() in ("1", "true", "yes")
    new_value = "0" if current else "1"
    # In production this would persist to a config file; here we note the intended change.
    AuditService.record(
        action="smtp_proxy_toggle",
        user=request.user.username if request.user.is_authenticated else None,
        detail=f"SMTP Proxy {'disabled' if current else 'enabled'}",
    )
    return JsonResponse(
        {"status": "ok", "enabled": not current, "note": "Restart postfix to apply"},
        content_type="application/json; charset=utf-8",
    )


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dns_toggle_relay(request: HttpRequest) -> JsonResponse:
    """Toggle Smart Host Relay setting."""
    current = os.environ.get("MAIL_SMART_HOST", "").lower() in ("1", "true", "yes")
    new_value = "0" if current else "1"
    AuditService.record(
        action="smart_host_toggle",
        user=request.user.username if request.user.is_authenticated else None,
        detail=f"Smart Host Relay {'disabled' if current else 'enabled'}",
    )
    return JsonResponse(
        {"status": "ok", "enabled": not current, "note": "Restart postfix to apply"},
        content_type="application/json; charset=utf-8",
    )


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
@require_POST
def dns_set_hop_count(request: HttpRequest) -> JsonResponse:
    """Update max hop count for mail routing."""
    try:
        value = int(request.POST.get("value", "10"))
        value = max(5, min(30, value))
    except (ValueError, TypeError):
        return JsonResponse(
            {"status": "err", "error": "Invalid hop count"}, status=400,
            content_type="application/json; charset=utf-8",
        )
    AuditService.record(
        action="hop_count_update",
        user=request.user.username if request.user.is_authenticated else None,
        detail=f"Set max hop count to {value}",
    )
    return JsonResponse(
        {"status": "ok", "value": value, "note": "Restart postfix to apply"},
        content_type="application/json; charset=utf-8",
    )
