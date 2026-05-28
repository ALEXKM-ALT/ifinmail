"""FileAttachableMixin — multiple-file / attachment support for models.

Usage:
    class Message(FileAttachableMixin, models.Model):
        content = models.TextField()
        # message.files.all() → queryset of StoredFile
        # message.images.all() → queryset of StoredFile (filtered to images)
"""

from django.db import models

from backend.apps.core.storage.models.stored_file import StoredFile


class FileAttachableMixin(models.Model):
    """Mixin that provides many-to-many file access on any model."""

    _files = models.ManyToManyField(
        StoredFile,
        blank=True,
        related_name="+",
    )

    @property
    def files(self) -> models.QuerySet[StoredFile]:
        return self._files.all()

    @property
    def images(self) -> models.QuerySet[StoredFile]:
        return self._files.filter(content_type__startswith="image/")

    class Meta:
        abstract = True
