"""accounts views package — re-exports all public view functions."""
from .auth import login_view, logout_view
from .branding import branding_identity, branding_reset, branding_save
from .dashboard import dashboard, dashboard_log_purge, dashboard_reboot, dashboard_rescan, dashboard_shell
from .logs import logs, logs_export, logs_full_history, logs_live_data
from .setup import setup_advance, setup_step, setup_wizard
from .spam import spam_add_provider, spam_filtering, spam_set_sensitivity
from .users import user_management, users_export, users_kill_sessions

__all__ = [
    "branding_identity",
    "branding_reset",
    "branding_save",
    "dashboard",
    "dashboard_log_purge",
    "dashboard_reboot",
    "dashboard_rescan",
    "dashboard_shell",
    "login_view",
    "logout_view",
    "logs",
    "logs_export",
    "logs_full_history",
    "logs_live_data",
    "setup_advance",
    "setup_step",
    "setup_wizard",
    "spam_add_provider",
    "spam_filtering",
    "spam_set_sensitivity",
    "user_management",
    "users_export",
    "users_kill_sessions",
]
