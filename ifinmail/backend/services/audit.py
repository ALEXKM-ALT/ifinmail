"""Audit trail service.

Persists audit events to the database via the AuditEvent model with
an in-memory fallback when the database is unavailable.  Keeps the
last 200 events in memory for fast dashboard access via get_recent().
Automatically purges the oldest DB records when the table exceeds
10,000 events.
"""

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger('backend')

# Lazy-import to avoid circular imports when models are not yet registered.
_AuditEvent = None


def _get_audit_model() -> Any:
    """Return the AuditEvent model class, importing it on first access."""
    global _AuditEvent
    if _AuditEvent is None:
        from backend.services.models import AuditEvent

        _AuditEvent = AuditEvent
    return _AuditEvent


class AuditService:
    """Central audit-trail service.

    In-memory buffer provides fast reads for dashboards; the database
    table provides durable, queryable long-term storage.
    """

    _events: list[dict] = []
    _max_memory_events: int = 200
    _max_db_events: int = 10_000

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def record(
        cls,
        action: str,
        user: str | None = None,
        detail: str = '',
        severity: str = 'info',
    ) -> None:
        """Record an audit event.

        Persists to the database first.  If the database is unreachable
        the event is still kept in the in-memory ring buffer so that
        dashboards are not left empty.
        """
        event_data = {
            'user': user or 'system',
            'action': action,
            'detail': detail,
            'severity': severity,
        }

        db_saved = cls._persist_to_db(event_data)

        # Always mirror to the in-memory buffer for fast reads.
        memory_event = {
            'time': datetime.now(UTC).isoformat(),
            **event_data,
        }
        cls._events.append(memory_event)
        if len(cls._events) > cls._max_memory_events:
            cls._events = cls._events[-cls._max_memory_events :]

        log_flag = '[db]' if db_saved else '[mem]'
        logger.info(
            'AUDIT %s: %s by %s — %s',
            log_flag,
            action,
            event_data['user'],
            detail,
        )

    @classmethod
    def get_recent(cls, limit: int = 50) -> list[dict]:
        """Return the *limit* most recent events from the in-memory buffer or database."""
        if not cls._events:
            try:
                audit_event = _get_audit_model()
                db_events = audit_event.objects.all()[:limit]
                cls._events = [
                    {
                        'time': e.time.isoformat() if hasattr(e.time, 'isoformat') else str(e.time),
                        'user': e.user,
                        'action': e.action,
                        'detail': e.detail,
                        'severity': e.severity,
                    }
                    for e in reversed(db_events)
                ]
            except Exception as exc:
                logger.warning('AUDIT: Failed to fetch recent events from DB — %s', exc)
        return cls._events[-limit:]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @classmethod
    def _persist_to_db(cls, event_data: dict) -> bool:
        """Create a database row and trigger purge if needed.

        Returns ``True`` on success, ``False`` when the database is not
        available.
        """
        try:
            audit_event = _get_audit_model()
            audit_event.objects.create(**event_data)
            cls._purge_old_events()
            return True
        except Exception as exc:
            logger.warning('AUDIT: DB persist failed — %s', exc)
            return False

    @classmethod
    def _purge_old_events(cls) -> None:
        """Delete the oldest records when the table exceeds the configured limit."""
        try:
            audit_event = _get_audit_model()
            total = audit_event.objects.count()
            if total <= cls._max_db_events:
                return

            excess = total - cls._max_db_events
            # Identify the ``excess`` oldest rows by time (ASC).
            doomed_ids = audit_event.objects.order_by('time').values_list('id', flat=True)[:excess]
            audit_event.objects.filter(id__in=list(doomed_ids)).delete()
            logger.info('AUDIT: Purged %d events (limit=%d)', excess, cls._max_db_events)
        except Exception as exc:
            logger.warning('AUDIT: Purge failed — %s', exc)
