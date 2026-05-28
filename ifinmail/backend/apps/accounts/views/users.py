"""User management view."""
import csv
import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from backend.apps.accounts.services import UserService
from backend.services.audit import AuditService

from .auth import _is_staff
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("backend")


def _admin_directory_rows() -> list[dict[str, str]]:
    """Return empty directory rows (placeholder until real user data integration)."""
    return []


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def user_management(request: HttpRequest) -> HttpResponse:
    """User management and governance screen."""
    return render(
        request,
        "admin/user_management.html",
        {
            "active_section": "users",
            "header_search_placeholder": "Search users or permissions...",
            "show_user_profile": True,
            "admin_headers": [_("Administrator"), _("Role"), _("Status"), _("Last Active")],
            "admins": _admin_directory_rows(),
            "is_mock": True,
            "mfa_adoption_pct": "98.2%",
            "active_sessions": "1,240",
            "session_domains": str(_("Across 42 domains")),
            "failed_logins": "43",
            "rbac_status": str(_("Optimal")),
            "unassigned_roles": str(_("0 Unassigned roles")),
            "role_counts": [
                {"name": str(_("Superuser")), "desc": str(_("Full system access")), "count": str(_("2 Users")), "badge_class": "ifinmail-badge--info"},
                {"name": str(_("Security Audit")), "desc": str(_("Logs & Monitor only")), "count": str(_("5 Users")), "badge_class": ""},
                {"name": str(_("Domain Operator")), "desc": str(_("Manage specific domains")), "count": str(_("12 Users")), "badge_class": ""},
            ],
            "live_sessions": [
                {"device": "Chrome on macOS", "detail": "IP: 192.168.1.45", "live": True},
                {"device": "iOS App v2.4", "detail": "IP: 72.14.21.102", "live": False, "ago": str(_("14m ago"))},
                {"device": str(_("SSH Terminal")), "detail": str(_("Root Console Access")), "live": True},
            ],
            "governance_items": [
                {"text": str(_("SSO Integration Active (Okta)")), "status": "ok"},
                {"text": str(_("Password Complexity: Hardened")), "status": "ok"},
                {"text": str(_("3 Keys expiring within 30 days")), "status": "warn"},
            ],
            "anomaly_bars": [45, 75, 66, 28, 82, 36],
            "anomaly_description": str(_("Spike detected in API token rotation from HK-based proxies.")),
            "audit_stats": {
                "jit_access": str(_("4 Approved")),
                "key_rotation": str(_("Last: 12h ago")),
                "manual_overrides": str(_("2 Pending Review")),
            },
        },
    )


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
def users_export(request: HttpRequest) -> HttpResponse:
    """Export all users as a CSV download."""
    try:
        users = UserService.get_all_users()
    except Exception:
        users = []

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = "attachment; filename=user_directory.csv"
    writer = csv.writer(response)
    writer.writerow(["Email", "Role", "Active", "Staff", "Superuser", "Created"])
    for u in users:
        writer.writerow([
            getattr(u, "email", ""),
            "Admin" if getattr(u, "is_staff", False) else "User",
            "Yes" if getattr(u, "is_active", False) else "No",
            "Yes" if getattr(u, "is_staff", False) else "No",
            "Yes" if getattr(u, "is_superuser", False) else "No",
            getattr(u, "created_at", ""),
        ])
    AuditService.record(
        action="users_export",
        user=request.user.username if request.user.is_authenticated else None,
        detail=f"Exported {len(users)} users",
    )
    return response


@login_required
@user_passes_test(_is_staff, login_url="accounts:login")
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
            action="sessions_killed",
            user=request.user.username if request.user.is_authenticated else None,
            detail=f"Terminated {killed} sessions",
            severity="warning",
        )
        return JsonResponse(
            {"status": "ok", "killed": killed},
            content_type="application/json; charset=utf-8",
        )
    except Exception as e:
        logger.exception("Failed to kill sessions: %s", e)
        return JsonResponse(
            {"status": "err", "error": str(e)}, status=500,
            content_type="application/json; charset=utf-8",
        )
