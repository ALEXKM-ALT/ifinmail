"""Dashboard view — live stats, service health, DNS status, activity."""

import json
import logging
import os
import shutil
import subprocess
from contextlib import suppress
from datetime import UTC
from typing import Any

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from backend.apps.accounts.services import UserService
from backend.apps.domains.services import DomainService
from backend.apps.mail.services import MailService
from backend.services.audit import AuditService
from backend.services.monitoring import MonitoringService

from ._constants import _APP_DIR, _LETSENCRYPT_DIR, _MAIL_VHOSTS_DIR
from .auth import _is_staff

logger = logging.getLogger('backend')


def _make_check(code: str, status_bool: bool, label: str) -> dict[str, str]:
    if status_bool:
        return {'check': code, 'status': 'pass', 'message': f'{label} verified'}
    return {'check': code, 'status': 'warn', 'message': f'Verify {label}'}


def _get_tls_expiry_days() -> dict[str, Any]:
    """Read TLS certificate and return days until expiry."""
    mail_hostname = os.environ.get('MAIL_HOSTNAME', '')
    domain = os.environ.get('DOMAIN', os.environ.get('MAIL_DOMAIN', ''))
    cert_paths = []
    if mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, 'live', mail_hostname, 'fullchain.pem'))
    if domain and domain != mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, 'live', domain, 'fullchain.pem'))

    if not cert_paths:
        return {'days': None, 'display': 'N/A', 'status': 'err'}

    if not shutil.which('openssl'):
        logger.error('openssl not found on PATH; cannot check TLS expiry')
        return {'days': None, 'display': 'N/A', 'status': 'err'}

    for cert_path in cert_paths:
        if not os.path.isfile(cert_path):
            continue
        try:
            import subprocess
            from datetime import datetime as dt

            result = subprocess.run(
                ['openssl', 'x509', '-enddate', '-noout', '-in', cert_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                continue
            date_str = result.stdout.strip().split('=', 1)[1]
            end_date = dt.strptime(date_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=UTC)
            days = (end_date - dt.now(UTC)).days
            return {
                'days': days,
                'display': f'{days}d',
                'status': 'ok' if days > 30 else ('warn' if days > 7 else 'err'),
            }
        except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.exception('Failed to read TLS certificate expiry: %s', e)
            continue

    return {'days': None, 'display': 'N/A', 'status': 'err'}


def _get_disk_usage() -> dict[str, object]:
    """Check disk usage on relevant mount points."""
    paths = os.environ.get('DISK_CHECK_PATHS', f'{_MAIL_VHOSTS_DIR},{_APP_DIR},/')
    for path in paths.split(','):
        path = path.strip()
        if os.path.exists(path):
            try:
                usage = shutil.disk_usage(path)
                free_gb = usage.free / (1024**3)
                total_gb = usage.total / (1024**3)
                pct = (usage.used / usage.total) * 100
                status = 'ok' if pct < 80 else ('warn' if pct < 95 else 'err')
                return {
                    'free_gb': round(free_gb, 1),
                    'total_gb': round(total_gb, 1),
                    'pct': round(pct, 1),
                    'display': f'{free_gb:.0f} GB',
                    'status': status,
                }
            except OSError:
                continue
    return {'free_gb': 0, 'total_gb': 0, 'pct': 0, 'display': 'N/A', 'status': 'warn'}


def _get_mail_volume_stats() -> dict[str, object]:
    """Check mail storage volume size."""
    mail_root = _MAIL_VHOSTS_DIR
    if not os.path.isdir(mail_root):
        return {'exists': False, 'display': 'N/A'}

    try:
        total_size = 0
        for dirpath, _dirnames, filenames in os.walk(mail_root):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                with suppress(OSError):
                    total_size += os.path.getsize(fp)
        mb = total_size / (1024 * 1024)
        if mb < 1:
            display = f'{total_size / 1024:.0f} KB'
        elif mb < 1024:
            display = f'{mb:.0f} MB'
        else:
            display = f'{mb / 1024:.1f} GB'
        return {'exists': True, 'display': display, 'bytes': total_size}
    except OSError as e:
        logger.error('Failed to walk mail volume at %s: %s', mail_root, e)
        return {'exists': True, 'display': 'unknown'}


def _get_stats() -> list[dict[str, object]]:
    """Fetch aggregate platform statistics."""
    db_ok = True
    try:
        domain_count = DomainService.get_domain_count()
        user_count = UserService.get_active_count()
        mailbox_count = MailService.get_mailbox_count()
    except OperationalError as e:
        logger.exception('Database error fetching platform stats: %s', e)
        db_ok = False
        domain_count = 0
        user_count = 0
        mailbox_count = 0

    try:
        disk = _get_disk_usage()
    except OSError as e:
        logger.error('Failed to get disk usage: %s', e)
        disk = {'free_gb': 0, 'total_gb': 0, 'pct': 0, 'display': 'N/A', 'status': 'warn'}
    cert_days = _get_tls_expiry_days()

    return [
        {'value': domain_count, 'label': 'Domains', 'status': 'ok' if db_ok else 'err'},
        {'value': user_count, 'label': 'Active Users', 'status': 'ok' if db_ok else 'err'},
        {'value': mailbox_count, 'label': 'Mailboxes', 'status': 'ok' if db_ok else 'err'},
        {
            'value': disk.get('display', 'N/A'),
            'label': 'Disk Free',
            'status': disk.get('status', 'warn'),
        },
        {
            'value': cert_days.get('display', 'N/A'),
            'label': 'TLS Expires',
            'status': cert_days.get('status', 'warn'),
        },
    ]


def _get_service_status() -> dict[str, dict[str, str]]:
    """Check health of core services — label reflects actual DB backend."""
    services = {}

    # Database — vendor-aware label (SQLite in dev, PostgreSQL in production)
    try:
        from django.db import connection as _conn
        from django.db import connections

        vendor = _conn.vendor
        _db_label = (
            'SQLite'
            if vendor == 'sqlite'
            else 'PostgreSQL'
            if vendor == 'postgresql'
            else vendor.capitalize()
        )
        with connections['default'].cursor() as c:
            c.execute('SELECT 1')
        services['database'] = {'label': _db_label, 'status': 'ok', 'detail': 'Connected'}
    except Exception:
        services['database'] = {'label': 'Database', 'status': 'err', 'detail': 'Unreachable'}

    # Cache (Redis in production; Django local-memory in dev — both report ok if working)
    try:
        cache.set('__dashboard_health', 1, timeout=5)
        if cache.get('__dashboard_health') == 1:
            services['cache'] = {'label': 'Cache', 'status': 'ok', 'detail': 'Connected'}
        else:
            services['cache'] = {'label': 'Cache', 'status': 'err', 'detail': 'Readback failed'}
    except Exception:
        services['cache'] = {'label': 'Cache', 'status': 'err', 'detail': 'Unreachable'}

    # TLS Certificate
    cert_days = _get_tls_expiry_days()
    if cert_days['days'] is not None:
        if cert_days['days'] > 30:
            s, d = 'ok', f'Valid for {cert_days["days"]}d'
        elif cert_days['days'] > 7:
            s, d = 'warn', f'Expires in {cert_days["days"]}d'
        else:
            s, d = 'err', f'Expiring in {cert_days["days"]}d'
    else:
        s, d = 'err', 'No certificate found'
    services['tls'] = {'label': 'TLS', 'status': s, 'detail': d}

    # Mail store — inferred from volume mount
    mail_data = _get_mail_volume_stats()
    if mail_data['exists']:
        services['mail-store'] = {
            'label': 'Mail Store',
            'status': 'ok',
            'detail': f'{mail_data["display"]} used',
        }
    else:
        services['mail-store'] = {
            'label': 'Mail Store',
            'status': 'warn',
            'detail': 'Volume not mounted',
        }

    return services


def _get_domains(request: HttpRequest) -> list[dict[str, object]]:
    """Fetch domain health from the database with pagination."""
    try:
        qs = DomainService.get_all_domains()
        paginator = Paginator(qs, 25)
        page_number = request.GET.get('page', 1)
        try:
            page_number = min(max(int(page_number), 1), 1000)
        except (ValueError, TypeError):
            page_number = 1
        page = paginator.get_page(page_number)
        rows = list(
            page.object_list.values_list(
                'name',
                'verified',
                'mx_verified',
                'spf_verified',
                'dkim_verified',
                'dmarc_verified',
            )
        )
    except Exception as e:
        logger.exception('Database error fetching domains: %s', e)
        rows = []

    # Return empty list — template shows a proper empty state with DNS link
    if not rows:
        return []

    domains = []
    for name, _verified, mx, spf, dkim, dmarc in rows:
        checks = [
            _make_check('mx', mx, 'MX record'),
            _make_check('spf', spf, 'SPF record'),
            _make_check('dkim', dkim, 'DKIM record'),
            _make_check('dmarc', dmarc, 'DMARC record'),
        ]
        warnings = []
        if not all([mx, spf, dkim, dmarc]):
            warnings.append('Missing DNS records — check deliverability')
        domains.append({'name': name, 'checks': checks, 'warnings': warnings})
    return domains


def _get_activity() -> list[dict[str, str]]:
    """Fetch recent audit events."""
    events = AuditService.get_recent(20)
    if not events:
        return [
            {
                'time': 'System started',
                'severity': 'info',
                'description': 'Audit log is active',
            }
        ]
    result = []
    for e in reversed(events):
        detail = f': {e["detail"]}' if e.get('detail') else ''
        result.append(
            {
                'time': e['time'].replace('T', ' ')[:16] if e.get('time') else '',
                'user': e.get('user', 'system'),
                'severity': e.get('severity', 'info'),
                'description': f'{e["user"]} - {e["action"]}{detail}',
            }
        )
    return result


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def dashboard(request: HttpRequest) -> HttpResponse:
    """Platform admin dashboard — live stats, service health, DNS status, activity."""
    stats = _get_stats()
    services = _get_service_status()
    domains = _get_domains(request)
    events = _get_activity()
    disk = _get_disk_usage()
    tls_days = _get_tls_expiry_days()
    tls_info = _get_tls_info()
    is_mock = not any([stats, services, domains, events])
    return render(
        request,
        'admin/dashboard.html',
        {
            'stats': stats,
            'services': services,
            'domains': domains,
            'domains_empty': len(domains) == 0,
            'events': events,
            'storage_used': disk.get('display', 'N/A'),
            'storage_pct': f'{disk.get("pct", 0):.0f}%',
            'storage_total': f'{disk.get("total_gb", 0):.1f} GB',
            'storage_status': disk.get('status', 'warn'),
            'storage_warning': str(_('Cleanup recommended')) if disk.get('status') == 'err' else '',
            'tls_days': tls_days,
            'tls_info': tls_info,
            'tls_info_json': json.dumps(tls_info),
            'mail_hostname': os.environ.get('MAIL_HOSTNAME', ''),
            'active_section': 'general',
            'header_search_placeholder': 'Search mail server logs...',
            'is_mock': is_mock,
        },
    )


def _get_tls_info() -> dict[str, Any]:
    """Return extended TLS certificate information (issuer, SANs, expiry)."""
    mail_hostname = os.environ.get('MAIL_HOSTNAME', '')
    domain = os.environ.get('DOMAIN', os.environ.get('MAIL_DOMAIN', ''))
    cert_paths = []
    if mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, 'live', mail_hostname, 'fullchain.pem'))
    if domain and domain != mail_hostname:
        cert_paths.append(os.path.join(_LETSENCRYPT_DIR, 'live', domain, 'fullchain.pem'))

    for cert_path in cert_paths:
        if not os.path.isfile(cert_path):
            continue
        info: dict[str, Any] = {'path': cert_path, 'issuer': '', 'sans': [], 'expiry_days': None}
        try:
            result = subprocess.run(
                ['openssl', 'x509', '-issuer', '-noout', '-in', cert_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                issuer_line = result.stdout.strip()
                if 'issuer=' in issuer_line:
                    info['issuer'] = issuer_line.split('issuer=', 1)[1].strip().strip('/')

            result = subprocess.run(
                ['openssl', 'x509', '-ext', 'subjectAltName', '-noout', '-in', cert_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                sans = []
                for line in result.stdout.strip().split('\n'):
                    line = line.strip().rstrip(',')
                    if line.startswith('DNS:'):
                        sans.append(line[4:])
                info['sans'] = sans

            expiry = _get_tls_expiry_days()
            info['expiry_days'] = expiry.get('days')
            info['expiry_status'] = expiry.get('status', 'err')
            return info
        except subprocess.TimeoutExpired:
            logger.error('TLS info: openssl timed out for %s', cert_path)
        except OSError as e:
            logger.exception('TLS info: OS error reading %s: %s', cert_path, e)
    return {}


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def dashboard_rescan(request: HttpRequest) -> JsonResponse:
    """Force a full rescan of DNS and TLS health for all domains."""
    results: dict[str, Any] = {'status': 'ok', 'domains': {}, 'tls': None}
    try:
        domains = DomainService.get_all_domains()
        for d in domains:
            dns_result = MonitoringService.check_dns(d.name)
            results['domains'][d.name] = dns_result

        results['tls'] = MonitoringService.check_tls_expiry()
        AuditService.record(
            action='dashboard_rescan',
            user=request.user.username if request.user.is_authenticated else None,
            detail=f'Rescanned {len(domains)} domain(s)',
        )
    except Exception as e:
        logger.exception('Rescan failed: %s', e)
        results['status'] = 'err'
        results['error'] = str(e)
    return JsonResponse(results, content_type='application/json; charset=utf-8')


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def dashboard_shell(request: HttpRequest) -> JsonResponse:
    """Disabled: shell execution from the web UI is not production-safe."""
    AuditService.record(
        action='shell_disabled',
        user=request.user.username if request.user.is_authenticated else None,
        detail='Blocked web shell invocation',
        severity='warning',
    )
    return JsonResponse(
        {'error': 'The web shell is disabled in production.'},
        status=403,
        content_type='application/json; charset=utf-8',
    )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def dashboard_log_purge(request: HttpRequest) -> JsonResponse:
    """Purge archived audit log entries, keeping the most recent 500."""
    try:
        audit_event = _get_audit_model_for_write()
        total_before = audit_event.objects.count()
        if total_before > 500:
            keep_ids = list(
                audit_event.objects.order_by('-time').values_list('id', flat=True)[:500]
            )
            deleted, _ = audit_event.objects.exclude(id__in=keep_ids).delete()
            AuditService.record(
                action='log_purge',
                user=request.user.username if request.user.is_authenticated else None,
                detail=f'Purged {deleted} audit entries (before={total_before})',
            )
            return JsonResponse(
                {
                    'status': 'ok',
                    'deleted': deleted,
                    'before': total_before,
                    'after': total_before - deleted,
                },
                content_type='application/json; charset=utf-8',
            )
        else:
            return JsonResponse(
                {'status': 'ok', 'deleted': 0, 'message': 'Below threshold — nothing to purge'},
                content_type='application/json; charset=utf-8',
            )
    except Exception as e:
        logger.exception('Log purge failed: %s', e)
        return JsonResponse(
            {'status': 'err', 'error': str(e)},
            status=500,
            content_type='application/json; charset=utf-8',
        )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def dashboard_reboot(request: HttpRequest) -> JsonResponse:
    """Disabled: service restarts must go through deployment automation."""
    AuditService.record(
        action='service_reboot_disabled',
        user=request.user.username if request.user.is_authenticated else None,
        detail='Blocked web-triggered service restart',
        severity='warning',
    )
    return JsonResponse(
        {
            'status': 'disabled',
            'services': {},
            'error': 'Use deployment automation to restart services.',
        },
        status=403,
        content_type='application/json; charset=utf-8',
    )


def _get_audit_model_for_write() -> Any:
    """Lazy-import AuditEvent for write operations."""
    from backend.services.models import AuditEvent

    return AuditEvent
