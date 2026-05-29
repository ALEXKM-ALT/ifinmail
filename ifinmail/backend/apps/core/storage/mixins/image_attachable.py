"""ImageAttachableMixin — single-image support for models (logos, thumbnails).

Usage:
    class Product(ImageAttachableMixin, models.Model):
        name = models.CharField(max_length=200)
        # product.primary_image → returns StoredFile or None
        # product.image_url → returns URL string or None
"""

from django.db import models

from backend.apps.core.storage.models.stored_file import StoredFile


class ImageAttachableMixin(models.Model):
    """Mixin that provides primary-image access on any model."""

    _primary_image = models.ForeignKey(
        StoredFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    @property
    def primary_image(self) -> StoredFile | None:
        return self._primary_image

    @property
    def image_url(self) -> str | None:
        if self._primary_image:
            return self._primary_image.file.url
        return None

    class Meta:
        abstract = True
