from django.db import models

from backend.apps.core.base.models.base import CoreModel


class Device(CoreModel):
    """Placeholder model for future device management (mobile clients, etc.)."""

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=64, blank=True, default="")
    identifier = models.CharField(max_length=512, unique=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        ordering = ["-last_seen"]

    def __str__(self) -> str:
        return self.name
