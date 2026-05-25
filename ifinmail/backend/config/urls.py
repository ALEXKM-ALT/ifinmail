"""
Root URL configuration for ifinmail.
"""
import logging

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

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


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("health/full/", health_full, name="health-full"),
    path("health/dns/", health_dns, name="health-dns"),
    path("health/deliverability/", health_deliverability, name="health-deliverability"),
    path("admin/", include("backend.apps.accounts.urls")),
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
handler404 = "backend.config.urls.custom_404"
handler500 = "backend.config.urls.custom_500"


def custom_404(request, exception=None):
    logger.warning("404 Not Found: %s", request.path)
    return JsonResponse(
        {"error": "Not found", "detail": "Resource not found"},
        status=404,
    )


def custom_500(request):
    logger.exception("500 Internal Server Error")
    return JsonResponse(
        {"error": "Internal server error", "detail": "An unexpected error occurred"},
        status=500,
    )
