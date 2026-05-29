"""User management view."""

import csv
import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from backend.apps.accounts.services import UserService
from backend.services.audit import AuditService

from .auth import _is_staff

logger = logging.getLogger('backend')


def _admin_directory_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for user in UserService.get_all_users():
        if not (user.is_staff or user.is_superuser):
            continue
        rows.append(
            {
                'name': user.email,
                'email': user.email,
                'role': 'Superuser' if user.is_superuser else 'Staff',
                'status': 'Active' if user.is_active else 'Inactive',
                'last_active': user.last_login.isoformat() if user.last_login else '',
            }
        )
    return rows


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def user_management(request: HttpRequest) -> HttpResponse:
    """User management and governance screen."""
    admins = _admin_directory_rows()
    active_sessions = Session.objects.count()
    superuser_count = sum(1 for admin in admins if admin['role'] == 'Superuser')
    staff_count = sum(1 for admin in admins if admin['role'] == 'Staff')

    return render(
        request,
        'admin/user_management.html',
        {
            'active_section': 'users',
            'header_search_placeholder': 'Search users or permissions...',
            'show_user_profile': True,
            'admin_headers': [_('Administrator'), _('Role'), _('Status'), _('Last Active')],
            'admins': admins,
            'is_mock': False,
            'mfa_adoption_pct': '0%',
            'active_sessions': str(active_sessions),
            'session_domains': str(_('Current Django sessions')),
            'failed_logins': '0',
            'rbac_status': str(_('Configured')),
            'unassigned_roles': str(_('No role audit configured')),
            'role_counts': [
                {
                    'name': str(_('Superuser')),
                    'desc': str(_('Full system access')),
                    'count': str(_('%(count)d Users') % {'count': superuser_count}),
                    'badge_class': 'ifinmail-badge--info',
                },
                {
                    'name': str(_('Staff')),
                    'desc': str(_('Admin console access')),
                    'count': str(_('%(count)d Users') % {'count': staff_count}),
                    'badge_class': '',
                },
            ],
            'live_sessions': [],
            'governance_items': [],
            'anomaly_bars': [],
            'anomaly_description': '',
            'audit_stats': {
                'jit_access': str(_('Not configured')),
                'key_rotation': str(_('Not configured')),
                'manual_overrides': str(_('0 Pending Review')),
            },
        },
    )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def users_export(request: HttpRequest) -> HttpResponse:
    """Export all users as a CSV download."""
    try:
        users = UserService.get_all_users()
    except Exception:
        users = []

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=user_directory.csv'
    writer = csv.writer(response)
    writer.writerow(['Email', 'Role', 'Active', 'Staff', 'Superuser', 'Created'])
    for u in users:
        writer.writerow(
            [
                getattr(u, 'email', ''),
                'Admin' if getattr(u, 'is_staff', False) else 'User',
                'Yes' if getattr(u, 'is_active', False) else 'No',
                'Yes' if getattr(u, 'is_staff', False) else 'No',
                'Yes' if getattr(u, 'is_superuser', False) else 'No',
                getattr(u, 'created_at', ''),
            ]
        )
    AuditService.record(
        action='users_export',
        user=request.user.username if request.user.is_authenticated else None,
        detail=f'Exported {len(users)} users',
    )
    return response


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def users_kill_sessions(request: HttpRequest) -> JsonResponse:
    """Terminate all user sessions except the current one."""
    try:
        current_session_key = request.session.session_key
        # Flush all sessions from the database except the current one
        sessions = Session.objects.all()
        killed = 0
        if current_session_key:
            sessions = sessions.exclude(session_key=current_session_key)
        for session in sessions:
            session.delete()
            killed += 1

        AuditService.record(
            action='sessions_killed',
            user=request.user.username if request.user.is_authenticated else None,
            detail=f'Terminated {killed} sessions',
            severity='warning',
        )
        return JsonResponse(
            {'status': 'ok', 'killed': killed},
            content_type='application/json; charset=utf-8',
        )
    except Exception as e:
        logger.exception('Failed to kill sessions: %s', e)
        return JsonResponse(
            {'status': 'err', 'error': str(e)},
            status=500,
            content_type='application/json; charset=utf-8',
        )
