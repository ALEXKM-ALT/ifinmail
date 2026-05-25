"""Audit trail service."""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("backend")


class AuditService:
    _events: list = []
    _max_events = 500

    @classmethod
    def record(
        cls,
        action: str,
        user: Optional[str] = None,
        detail: str = "",
        severity: str = "info",
    ):
        event = {
            "time": datetime.now(timezone.utc).isoformat(),
            "user": user or "system",
            "action": action,
            "detail": detail,
            "severity": severity,
        }
        cls._events.append(event)
        if len(cls._events) > cls._max_events:
            cls._events = cls._events[-cls._max_events:]
        logger.info("AUDIT: %s by %s — %s", action, user or "system", detail)

    @classmethod
    def get_recent(cls, limit: int = 50):
        return cls._events[-limit:]
