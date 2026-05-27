import uuid

from django.db import models


class CoreModel(models.Model):
    """Abstract base model for all ifinmail models.

    Provides a UUID primary key and standard timestamp fields.
    Every model in the ifinmail platform must inherit from this base
    (AGENTS.md § Governance — Core Apps).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
