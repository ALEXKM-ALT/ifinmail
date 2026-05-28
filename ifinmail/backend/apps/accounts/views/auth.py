"""Authentication views: login, logout, staff check."""
import logging

from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie

from backend.services.audit import AuditService

from ._constants import _ALLOWED_HOST_NAMES

logger = logging.getLogger("backend")


_RATE_LIMIT_MAX = 10  # max login attempts
_RATE_LIMIT_WINDOW = 300  # per 5 minutes


def _is_staff(user: object) -> bool:
    """Check staff status with database revalidation."""
    if not user.is_authenticated:
        return False
    try:
        user.refresh_from_db(fields=["is_staff", "is_superuser", "is_active"])
    except ObjectDoesNotExist:
        logger.warning("User object disappeared during staff check")
        return False
    if not user.is_active:
        return False
    return user.is_staff or user.is_superuser


def _get_client_ip(request: HttpRequest) -> str:
    """Extract client IP from request headers."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@ensure_csrf_cookie
def login_view(request: HttpRequest) -> HttpResponse:
    """Admin login view."""
    error = None

    # Rate-limit check (backup for Axes)
    client_ip = _get_client_ip(request)
    rate_key = f"login_rate:{client_ip}"
    attempts = cache.get(rate_key, 0)
    if attempts >= _RATE_LIMIT_MAX:
        logger.warning("Rate limit exceeded for IP %s", client_ip)
        error = "Too many login attempts. Try again later."
        return render(request, "admin/login.html", {"error": error})

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        # Check for Axes lockout before attempting auth
        try:
            from axes.helpers import get_lockout_message, is_already_locked
            from axes.conf import settings as axes_settings

            if callable(axes_settings.AXES_LOCKOUT_CALLABLE):
                credentials = {"username": email, "ip_address": request.META.get("REMOTE_ADDR", "")}
                if axes_settings.AXES_LOCKOUT_CALLABLE(request, credentials):
                    error = get_lockout_message(request) or "Account locked. Try again later."
                    AuditService.record(
                        "login_blocked",
                        user=email,
                        detail="Account locked by Axes",
                        severity="warn",
                    )
                    return render(request, "admin/login.html", {"error": error})
            elif is_already_locked(request):
                error = get_lockout_message(request) or "Account locked. Try again later."
                AuditService.record(
                    "login_blocked",
                    user=email,
                    detail="Account locked by Axes",
                    severity="warn",
                )
                return render(request, "admin/login.html", {"error": error})
        except ImportError:
            pass

        user = authenticate(request, username=email, password=password)
        if user is not None:
            # Clear rate-limit on success
            cache.delete(rate_key)

            request.session.cycle_key()
            login(request, user)

            AuditService.record(
                "login_success",
                user=user.email,
                detail=f"IP: {client_ip}",
                severity="info",
            )

            next_url = request.GET.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts=_ALLOWED_HOST_NAMES or None,
            ):
                return redirect(next_url)
            return redirect("accounts:dashboard")

        # Increment rate-limit on failure
        cache.set(rate_key, attempts + 1, _RATE_LIMIT_WINDOW)

        AuditService.record(
            "login_failed",
            user=email,
            detail=f"IP: {client_ip}",
            severity="warn",
        )
        error = "Invalid email or password."
    return render(request, "admin/login.html", {"error": error})


def logout_view(request: HttpRequest) -> HttpResponse:
    """Admin logout view — fully flush session to prevent reuse across tabs."""
    AuditService.record(
        "logout",
        user=getattr(request.user, "email", "unknown"),
        detail="User logged out",
        severity="info",
    )
    request.session.flush()
    logout(request)
    return redirect("accounts:login")
