"""In-memory maintenance mode toggle for read-only API state."""

import logging
import json

logger = logging.getLogger("ifinmail.maintenance")

_enabled = False


def enable() -> None:
    global _enabled
    _enabled = True
    logger.warning("MAINTENANCE MODE ENABLED — API is now read-only")


def disable() -> None:
    global _enabled
    _enabled = False
    logger.info("Maintenance mode disabled")


def is_enabled() -> bool:
    return _enabled


class MaintenanceMiddleware:
    """Reject non-read requests when maintenance mode is on."""

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and _enabled:
            method = scope.get("method", "GET")
            path = scope.get("path", "/")

            if method not in self.SAFE_METHODS and not path.startswith("/admin/maintenance"):
                body = json.dumps({"detail": "Service temporarily in maintenance mode"}).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", b"3600"),
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })
                return

        await self.app(scope, receive, send)
