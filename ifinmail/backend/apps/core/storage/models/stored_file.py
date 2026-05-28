import os
import uuid

from django.db import models

from backend.apps.core.base.models.base import CoreModel
from backend.apps.core.types.enums import EntityType, StorageVisibility


def _upload_to(instance: "StoredFile", filename: str) -> str:
    """Generate unique, collision-resistant upload paths (EC-76).
    Uses UUIDs to prevent filename collisions and race conditions.
    """
    ext = os.path.splitext(filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return os.path.join("storage", instance.entity_type or "unknown", unique_name)


class StoredFile(CoreModel):
    """Central file storage model — single source of truth for all media.
    AGENTS.md § Storage Architecture: ALL media/files MUST use this model.
    """

    file = models.FileField(upload_to=_upload_to)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255)
    size_bytes = models.BigIntegerField()
    entity_type = models.CharField(
        max_length=32,
        choices=[(e.value, e.name) for e in EntityType],
    )
    entity_id = models.UUIDField(null=True, blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=[(v.value, v.name) for v in StorageVisibility],
        default=StorageVisibility.PRIVATE.value,
    )

    class Meta:
        db_table = "ifinmail_stored_file"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
        ]
