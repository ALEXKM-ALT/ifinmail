"""DNS API views — JSON endpoints (API flow)."""
import logging
import os

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from backend.apps.dns.services import DNSService
from backend.services.monitoring import MonitoringService

from ._helpers import PROVIDER_MAP, _build_records, _get_server_ip, _is_staff

logger = logging.getLogger("backend")


@require_POST
@ensure_csrf_cookie
@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_configure(request: HttpRequest) -> JsonResponse:
    """POST endpoint: configure DNS records via the selected provider."""
    provider_name = request.POST.get("provider", "").lower()
    domain = request.POST.get("domain", os.environ.get("DOMAIN", ""))

    if provider_name not in PROVIDER_MAP:
        return JsonResponse({"success": False, "message": f"Unknown provider: {provider_name}"}, status=400)

    cls, fields, _ = PROVIDER_MAP[provider_name]
    creds = {f: request.POST.get(f, "").strip() for f in fields}
    if not all(creds.values()):
        missing = [f for f, v in creds.items() if not v.strip()]
        return JsonResponse({"success": False, "message": f"Missing credentials: {', '.join(missing)}"}, status=400)

    DNSService.update_or_create_config(
        provider_name=provider_name,
        credentials=creds,
    )

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
            "propagation_note": "DNS changes may take up to 48 hours to propagate. Verify after a few minutes.",
        })
    except Exception as e:
        logger.exception("DNS configuration failed for %s via %s", domain, provider_name)
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def dns_status(request: HttpRequest) -> JsonResponse:
    """GET endpoint: return current DNS record verification status."""
    domain = request.GET.get("domain", os.environ.get("DOMAIN", os.environ.get("MAIL_DOMAIN", "")))
    try:
        status = MonitoringService.check_dns(domain)
        return JsonResponse({"domain": domain, "records": status})
    except Exception as e:
        return JsonResponse({"domain": domain, "error": str(e)}, status=500)
