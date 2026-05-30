"""Logs view — system logs and audit trail."""

import csv
import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from backend.services.audit import AuditService

from .auth import _is_staff

logger = logging.getLogger('backend')

_AUDIT_PAGE_SIZE = 20


def _admin_log_rows(level: str = '') -> list[dict[str, str]]:
    """Return audit events filtered by level for the logs table."""
    events = AuditService.get_recent(50)
    rows = []
    for e in reversed(events):
        severity = e.get('severity', 'info')
        if level and severity.lower() != level.lower():
            continue
        rows.append(
            {
                'timestamp': e.get('time', '').replace('T', ' ')[:19] if e.get('time') else '',
                'level': severity.upper(),
                'service': e.get('action', 'system'),
                'message': e.get('detail', '') or e.get('action', ''),
            }
        )
    return rows


def _admin_audit_items(page: int = 1, level: str = '') -> list[dict[str, str]]:
    """Return paginated audit trail items."""
    events = AuditService.get_recent(200)
    items = []
    for e in reversed(events):
        severity = e.get('severity', 'info')
        if level and severity.lower() != level.lower():
            continue
        items.append(
            {
                'type': severity.upper(),
                'title': e.get('action', 'Event'),
                'body': e.get('detail', ''),
                'actor': e.get('user', 'system'),
                'age': e.get('time', '').replace('T', ' ')[:19] if e.get('time') else '',
            }
        )
    paginator = Paginator(items, _AUDIT_PAGE_SIZE)
    try:
        page_num = min(max(int(page), 1), paginator.num_pages)
    except (ValueError, TypeError):
        page_num = 1
    return list(paginator.get_page(page_num).object_list)


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def logs(request: HttpRequest) -> HttpResponse:
    """System logs and audit trail screen."""
    level = request.GET.get('level', '').strip().upper()
    page = request.GET.get('page', '1')
    try:
        page_num = int(page)
    except (ValueError, TypeError):
        page_num = 1

    log_rows = _admin_log_rows(level=level)
    audit_items = _admin_audit_items(page=page_num, level=level)
    is_mock = len(log_rows) == 0 and len(audit_items) == 0

    return render(
        request,
        'admin/logs.html',
        {
            'active_section': 'logs',
            'header_search_placeholder': 'Search system logs...',
            'log_headers': [_('Timestamp'), _('Level'), _('Service'), _('Message')],
            'log_rows': log_rows,
            'log_empty_message': _('No log data available — telemetry not yet integrated'),
            'audit_items': audit_items,
            'is_mock': is_mock,
            'current_level': level,
            'current_page': page_num,
            'has_more': len(audit_items) >= _AUDIT_PAGE_SIZE,
        },
    )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def logs_export(request: HttpRequest) -> HttpResponse:
    """Export audit events as a CSV download."""
    level = request.GET.get('level', '').strip().upper()
    events = AuditService.get_recent(500)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=audit_log.csv'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Level', 'Service/Action', 'Message', 'User'])
    for e in reversed(events):
        severity = e.get('severity', 'info')
        if level and severity.upper() != level:
            continue
        writer.writerow(
            [
                e.get('time', '').replace('T', ' ')[:19],
                severity.upper(),
                e.get('action', ''),
                e.get('detail', ''),
                e.get('user', 'system'),
            ]
        )
    return response


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def logs_live_data(request: HttpRequest) -> JsonResponse:
    """Return the latest log entries as JSON for polling-based live view."""
    level = request.GET.get('level', '').strip().upper()
    rows = _admin_log_rows(level=level)
    # Return only the most recent 10 entries for polling efficiency
    return JsonResponse(
        {'rows': rows[-10:] if len(rows) > 10 else rows},
        content_type='application/json; charset=utf-8',
    )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def logs_full_history(request: HttpRequest) -> HttpResponse:
    """Paginated full audit history page."""
    return logs(request)
