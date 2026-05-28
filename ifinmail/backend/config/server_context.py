"""
Server-level context processor — injects server metadata into every template.
Values read from environment variables with sensible fallbacks.
"""
from __future__ import annotations

import os


def server_context(request: object) -> dict[str, object]:
    """Context processor — injects server metadata into every template context."""
    version = os.environ.get("APP_VERSION", "v2.4.0-stable")
    support_email = os.environ.get("SUPPORT_EMAIL", "support@ifinmail.io")
    docs_url = os.environ.get("DOCS_URL", "https://ifinmail.dev/docs")
    server_status = os.environ.get("SERVER_STATUS", "Online")
    return {
        "server_version": version,
        "support_email": support_email,
        "docs_url": docs_url,
        "server_status": server_status,
        "notification_count": 0,
    }
