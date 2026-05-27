"""
Root URL configuration for ifinmail.
"""
import logging

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.shortcuts import redirect, render

from backend.apps.mail.views import autoconfig_mozilla, autoconfig_outlook

logger = logging.getLogger("backend")


def health_check(request):
    """Health check endpoint for load balancers and monitoring."""
    from django.db import connections
    from django.db.utils import OperationalError

    status = {"status": "ok", "database": "ok"}
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError:
        status["database"] = "unreachable"
        status["status"] = "degraded"

    http_status = 200 if status["status"] == "ok" else 503
    return JsonResponse(status, status=http_status)


def health_full(request):
    """Full system health check — database, redis, TLS, disk."""
    from backend.services.monitoring import MonitoringService

    health = MonitoringService.get_full_health()
    http_status = 200 if health["status"] == "ok" else (503 if health["status"] == "err" else 200)
    return JsonResponse(health, status=http_status)


def health_dns(request):
    """DNS health check for configured domains."""
    import os

    from backend.apps.domains.models import Domain
    from backend.services.monitoring import MonitoringService

    domains_data = {}
    try:
        for domain in Domain.objects.order_by("name"):
            domains_data[domain.name] = MonitoringService.check_dns(domain.name)
    except Exception:
        fallback = os.environ.get("MAIL_DOMAIN", os.environ.get("DOMAIN", ""))
        domains_data[fallback] = MonitoringService.check_dns(fallback)

    all_pass = all(
        all(r["status"] == "pass" for r in records.values())
        for records in domains_data.values()
    )
    return JsonResponse({
        "status": "ok" if all_pass else "warn",
        "domains": domains_data,
    })


def health_deliverability(request):
    """Deliverability check — DNS propagation, blacklists, rDNS, port 25, TLS."""
    domain = request.GET.get("domain", "")
    from backend.services.deliverability import DeliverabilityService
    result = DeliverabilityService.run_all_checks(domain=domain or None)
    http_status = 200 if result.get("status") != "fail" else 503
    return JsonResponse(result, status=http_status)


def legacy_accounts_redirect(request, path=""):
    # EC-44: Redirect /admin/ directly to dashboard (avoid double redirect chain)
    from django.urls import reverse
    target = reverse("accounts:dashboard") if not path else f"/accounts/{path}"
    return redirect(target, permanent=False)


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("health/full/", health_full, name="health-full"),
    path("health/dns/", health_dns, name="health-dns"),
    path("health/deliverability/", health_deliverability, name="health-deliverability"),
    path("accounts/", include("backend.apps.accounts.urls")),
    path("admin/", legacy_accounts_redirect),
    path("admin/<path:path>", legacy_accounts_redirect),
    path("manage-panel/", admin.site.urls),
    path("mail/", include("backend.apps.mail.urls")),
    path("domains/", include("backend.apps.domains.urls")),
    path("devices/", include("backend.apps.devices.urls")),
    path("dns/", include("backend.apps.dns.urls")),
    # Email client autoconfiguration
    path(".well-known/autoconfig/mail/config-v1.1.xml", autoconfig_mozilla, name="autoconfig-mozilla"),
    path("mail/config-v1.1.xml", autoconfig_mozilla, name="autoconfig-mozilla-alt"),
    path("autodiscover/autodiscover.xml", autoconfig_outlook, name="autoconfig-outlook"),
]

# Custom error handlers
handler400 = "backend.config.urls.custom_400"
handler403 = "backend.config.urls.custom_403"
handler404 = "backend.config.urls.custom_404"
handler500 = "backend.config.urls.custom_500"


def _wants_html(request):
    accept = request.META.get("HTTP_ACCEPT", "")
    if "text/html" in accept:
        return True
    if accept in ("", "*/*") and not request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return True
    return False


def custom_400(request, exception=None):
    logger.warning("400 Bad Request: %s", request.path)
    if _wants_html(request):
        return render(request, "400.html", status=400)
    return JsonResponse(
        {"error": "Bad request", "detail": str(exception) if exception else "Invalid request"},
        status=400,
    )


def custom_403(request, exception=None):
    logger.warning("403 Forbidden: %s", request.path)
    if _wants_html(request):
        return render(request, "403.html", status=403)
    return JsonResponse(
        {"error": "Forbidden", "detail": "You do not have permission to access this resource"},
        status=403,
    )


def custom_404(request, exception=None):
    logger.warning("404 Not Found: %s", request.path)
    if _wants_html(request):
        return render(request, "404.html", status=404)
    return JsonResponse(
        {"error": "Not found", "detail": "Resource not found"},
        status=404,
    )


def custom_500(request):
    logger.exception("500 Internal Server Error")
    if _wants_html(request):
        return render(request, "500.html", status=500)
    return JsonResponse(
        {"error": "Internal server error", "detail": "An unexpected error occurred"},
        status=500,
    )
