"""StorageService — single interface for all file uploads.

Usage:
    from backend.apps.core.storage.services.storage_service import StorageService

    result = StorageService.upload(
        merchant_id=merchant.id,
        file=uploaded_file,
        user=request.user,
        entity_type='PRODUCT',
        entity_id=product.id,
    )
"""

import logging
import os

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from backend.apps.core.storage.models.stored_file import StoredFile

logger = logging.getLogger(__name__)

# Allowed file extensions and their max sizes (EC-73, EC-74)
_ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".txt", ".csv", ".json", ".xml",
    ".zip", ".gz", ".tar",
}
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

# Allowed MIME types mapped from extensions for server-side verification
_EXTENSION_MIME_MAP = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".svg": {"image/svg+xml"},
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xls": {"application/vnd.ms-excel"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".txt": {"text/plain"},
    ".csv": {"text/csv"},
    ".json": {"application/json"},
    ".xml": {"application/xml", "text/xml"},
    ".zip": {"application/zip"},
    ".gz": {"application/gzip"},
    ".tar": {"application/x-tar"},
}


class StorageService:
    """Centralised storage operations — the ONLY way to persist files."""

    @staticmethod
    def upload(
        *,
        file: UploadedFile,
        user,
        entity_type: str,
        entity_id: str = "",
        merchant_id: str = "",
    ) -> StoredFile:
        """Persist an uploaded file and return the StoredFile record.

        Validates file extension, MIME type, and size before persisting
        (EC-73, EC-74).
        """
        original_name = file.name or "unknown"
        ext = os.path.splitext(original_name)[1].lower()

        # EC-73: Validate file extension against allowlist
        if ext not in _ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File type '.{ext}' is not allowed. "
                f"Allowed types: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            )

        # EC-73: Validate MIME type against extension (server-side verification)
        client_mime = (file.content_type or "").lower()
        expected_mimes = _EXTENSION_MIME_MAP.get(ext, set())
        if expected_mimes and client_mime not in expected_mimes:
            raise ValidationError(
                f"Content-Type '{client_mime}' does not match file extension '{ext}'."
            )

        # EC-74: Enforce file size limit
        if file.size > _MAX_UPLOAD_SIZE:
            raise ValidationError(
                f"File size ({file.size} bytes) exceeds maximum ({_MAX_UPLOAD_SIZE} bytes)."
            )

        stored = StoredFile.objects.create(
            file=file,
            original_filename=original_name,
            content_type=client_mime or "application/octet-stream",
            size_bytes=file.size,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        return stored
