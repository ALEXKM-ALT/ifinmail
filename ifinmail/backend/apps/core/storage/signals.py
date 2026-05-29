"""Signal handlers for the storage app (EC-77)."""

import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from backend.apps.core.storage.models.stored_file import StoredFile

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=StoredFile)
def _delete_file_on_disk(sender: type[StoredFile], instance: StoredFile, **kwargs: object) -> None:
    """Delete the physical file from storage when a StoredFile record is
    removed (EC-77). Prevents orphaned files from consuming disk space.
    """
    if instance.file and instance.file.name:
        try:
            instance.file.delete(save=False)
        except (OSError, FileNotFoundError) as exc:
            logger.warning(
                'Could not delete file %s for StoredFile %s: %s',
                instance.file.name,
                instance.id,
                exc,
            )
