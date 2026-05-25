from django.db import models


class Device(models.Model):
    """Placeholder model for future device management (mobile clients, etc.)."""

    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=64, blank=True, default="")
    identifier = models.CharField(max_length=512, unique=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        ordering = ["-last_seen"]

    def __str__(self):
        return self.name
