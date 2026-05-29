"""
Root URL configuration for ifinmail.
"""

import logging

from django.contrib import admin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import include, path

from backend.apps.mail.web import autoconfig_mozilla, autoconfig_outlook

logger = logging.getLogger('backend')


def health_check(request: HttpRequest) -> JsonResponse:
    """Health check endpoint for load balancers and monitoring."""
    from django.db import connections
    from django.db.utils import OperationalError

    status = {'status': 'ok', 'database': 'ok'}
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
    except OperationalError:
        status['database'] = 'unreachable'
        status['status'] = 'degraded'

    http_status = 200 if status['status'] == 'ok' else 503
    return JsonResponse(status, status=http_status, content_type='application/json; charset=utf-8')


def health_full(request: HttpRequest) -> JsonResponse:
    """Full system health check — database, redis, TLS, disk."""
    from backend.services.monitoring import MonitoringService

    health = MonitoringService.get_full_health()
    http_status = 200 if health['status'] == 'ok' else (503 if health['status'] == 'err' else 200)
    return JsonResponse(health, status=http_status, content_type='application/json; charset=utf-8')


def health_dns(request: HttpRequest) -> JsonResponse:
    """DNS health check for configured domains."""
    import os

    from backend.apps.domains.services import DomainService
    from backend.services.monitoring import MonitoringService

    domains_data = {}
    try:
        for domain in DomainService.get_all_domains():
            domains_data[domain.name] = MonitoringService.check_dns(domain.name)
    except Exception:
        fallback = os.environ.get('MAIL_DOMAIN', os.environ.get('DOMAIN', ''))
        domains_data[fallback] = MonitoringService.check_dns(fallback)

    all_pass = all(
        all(r['status'] == 'pass' for r in records.values()) for records in domains_data.values()
    )
    return JsonResponse(
        {
            'status': 'ok' if all_pass else 'warn',
            'domains': domains_data,
        },
        content_type='application/json; charset=utf-8',
    )


def health_deliverability(request: HttpRequest) -> JsonResponse:
    """Deliverability check — DNS propagation, blacklists, rDNS, port 25, TLS."""
    domain = request.GET.get('domain', '')
    from backend.services.deliverability import DeliverabilityService

    result = DeliverabilityService.run_all_checks(domain=domain or None)
    http_status = 200 if result.get('status') != 'fail' else 503
    return JsonResponse(result, status=http_status, content_type='application/json; charset=utf-8')


def legacy_accounts_redirect(request: HttpRequest, path: str = '') -> HttpResponse:
    # EC-44: Redirect /admin/ directly to dashboard (avoid double redirect chain)
    from django.urls import reverse

    target = reverse('accounts:dashboard') if not path else f'/accounts/{path}'
    return redirect(target, permanent=False)


def landing_page(request: HttpRequest) -> HttpResponse:
    """Public landing page — no authentication required."""
    return render(request, 'landing.html')


def terms_page(request: HttpRequest) -> HttpResponse:
    """Public terms of service page."""
    return render(request, 'terms.html')


def privacy_page(request: HttpRequest) -> HttpResponse:
    """Public privacy policy page."""
    return render(request, 'privacy.html')


urlpatterns = [
    path('', landing_page, name='landing'),
    path('terms/', terms_page, name='terms'),
    path('privacy/', privacy_page, name='privacy'),
    path('health/', health_check, name='health-check'),
    path('health/full/', health_full, name='health-full'),
    path('health/dns/', health_dns, name='health-dns'),
    path('health/deliverability/', health_deliverability, name='health-deliverability'),
    path('accounts/', include('backend.apps.accounts.urls')),
    path('admin/', legacy_accounts_redirect),
    path('admin/<path:path>', legacy_accounts_redirect),
    path('manage-panel/', admin.site.urls),
    path('domains/', include('backend.apps.domains.urls')),
    path('devices/', include('backend.apps.devices.urls')),
    path('dns/', include('backend.apps.dns.urls')),
    # Email client autoconfiguration
    path(
        '.well-known/autoconfig/mail/config-v1.1.xml', autoconfig_mozilla, name='autoconfig-mozilla'
    ),
    path('mail/config-v1.1.xml', autoconfig_mozilla, name='autoconfig-mozilla-alt'),
    path('autodiscover/autodiscover.xml', autoconfig_outlook, name='autoconfig-outlook'),
]

# Custom error handlers
ERROR_HANDLERS: dict[int, tuple[str, str, str, str, str]] = {
    400: ('400 Bad Request: %s', 'Bad request', 'Invalid request', 'warn', '400.html'),
    403: (
        '403 Forbidden: %s',
        'Forbidden',
        'You do not have permission to access this resource',
        'warn',
        '403.html',
    ),
    404: ('404 Not Found: %s', 'Not found', 'Resource not found', 'warn', '404.html'),
    500: (
        '500 Internal Server Error',
        'Internal server error',
        'An unexpected error occurred',
        'exception',
        '500.html',
    ),
    502: ('502 Bad Gateway: %s', 'Bad gateway', 'Invalid upstream response', 'warn', '502.html'),
    503: (
        '503 Service Unavailable: %s',
        'Service unavailable',
        'Temporarily unavailable',
        'warn',
        '503.html',
    ),
    504: ('504 Gateway Timeout: %s', 'Gateway timeout', 'Upstream timed out', 'warn', '504.html'),
}

for _code in (400, 403, 404, 500, 502, 503, 504):
    globals()[f'handler{_code}'] = f'backend.config.urls.custom_error_{_code}'


def _make_error_handler(status_code: int):
    log_msg, json_error, json_detail, log_level, template = ERROR_HANDLERS[status_code]

    def handler(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
        path = request.path
        try:
            if log_level == 'exception':
                logger.exception(log_msg, path)
            else:
                logger.log(getattr(logging, log_level.upper(), logging.WARNING), log_msg, path)
        except Exception:
            # Never let logging failures cascade
            pass

        if _wants_html(request):
            try:
                return render(
                    request,
                    template,
                    {
                        'error_code': str(status_code),
                        'error_title': json_error.title(),
                        'error_description': str(exception) if exception is not None else '',
                        'error_detail': json_detail,
                    },
                    status=status_code,
                )
            except Exception:
                # Fall back to JSON if template rendering fails
                pass

        return JsonResponse(
            {'error': json_error, 'detail': json_detail},
            status=status_code,
            content_type='application/json; charset=utf-8',
        )

    return handler


def _wants_html(request: HttpRequest) -> bool:
    accept = request.META.get('HTTP_ACCEPT', '')
    if 'text/html' in accept:
        return True
    # */* or empty accept means client accepts anything — prefer JSON for API safety
    # Most browsers explicitly send text/html; only API clients send bare */*
    if accept in ('', '*/*'):
        return False
    return False


for _code in ERROR_HANDLERS:
    globals()[f'custom_error_{_code}'] = _make_error_handler(_code)
