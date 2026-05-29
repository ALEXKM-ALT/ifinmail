"""Models for backend services.

Contains the AuditEvent model used by AuditService for persistent
audit trail storage.
"""

import uuid

from django.db import models


class AuditEvent(models.Model):
    """Persistent audit trail event.

    Managed by Django (not read from init-db.sh).  Automatically
    purges the oldest records when the total exceeds 10,000 events.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    severity = models.CharField(max_length=32, default='info')

    class Meta:
        managed = True
        db_table = 'ifinmail_audit_event'
        ordering = ['-time']

    def __str__(self) -> str:
        return f'{self.action} by {self.user} at {self.time}'
