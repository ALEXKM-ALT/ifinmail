# File Upload & Storage — Edge Cases (73–81)

## EC-73: No File Type Validation on Upload
**File:** `core/storage/services/storage_service.py` (implied by `StoredFile` model)
**Risk:** High — Arbitrary file upload
**Status:** ✅ Fixed — Added extension allowlist and MIME-type verification in `StorageService.upload()`
**Description:** `StorageService.upload()` accepts any `file` object. The `content_type` field is populated from the upload, but there is no validation that the content type matches the actual file contents. An attacker can upload a malicious file (e.g., a PHP webshell) disguised as a JPEG. If served directly, this could lead to remote code execution.
**Trigger:** Uploading a .php file with Content-Type: image/jpeg.
**Fix:** Validate file magic bytes against the declared content type. Use a library like `python-magic` for server-side MIME detection.

---

## EC-74: No File Size Validation Beyond Django's DATA_UPLOAD_MAX_MEMORY_SIZE
**File:** `settings/base.py:125`
**Risk:** Medium — Disk exhaustion
**Status:** ✅ Fixed — Added 50MB size limit in `StorageService.upload()`
**Description:** `DATA_UPLOAD_MAX_MEMORY_SIZE = 2.5MB` only limits in-memory upload size, not total file size. Nginx has `client_max_body_size 50M` which limits HTTP request body size. Within the application, there is no per-file size limit. A 49MB file upload bypasses the in-memory limit (spilled to disk as a temp file) and could exhaust disk space if done repeatedly.
**Trigger:** Uploading many large files (e.g., 49MB each).
**Fix:** Add explicit file size validation in `StorageService.upload()` before persisting to disk.

---

## EC-75: Uploaded Files Stored Without Access Control
**File:** `core/storage/models/stored_file.py`
**Risk:** High — Unauthorized file access
**Description:** The `StoredFile` model has a `visibility` field (PRIVATE/INTERNAL/PUBLIC) but there is no middleware or view-level enforcement of these visibility levels. Any authenticated user (or even unauthenticated user if the file URL is guessable) can access files at `/media/storage/<filename>`. There is no permission check before serving files.
**Trigger:** Guessing or enumerating uploaded file URLs.
**Fix:** Serve uploaded files through a Django view that checks user permissions and visibility level, rather than directly from the filesystem via `MEDIA_URL`.

---

## EC-76: Filename Collisions and Race Conditions in `upload_to`
**File:** `core/storage/models/stored_file.py:12`
**Risk:** Medium — File overwrite
**Description:** The `FileField(upload_to="storage/")` uses a flat directory with no subdirectory structure and no unique filename suffix. If two users upload files with the same original filename simultaneously, Django's upload handler creates a collision. The second upload overwrites the first file on disk (though the database record still references the old file path).
**Trigger:** Two concurrent uploads with the same filename.
**Fix:** Generate unique filenames using UUIDs or `{entity_type}/{entity_id}/{uuid}_{original_name}` pattern.

---

## EC-77: Orphaned Files on Disk When StoredFile Record is Deleted
**File:** Not implemented
**Risk:** Medium — Disk space leak
**Status:** ✅ Fixed — Added `post_delete` signal handler that removes the physical file
**Description:** There is no signal handler or service method to delete the underlying file from disk when a `StoredFile` record is deleted. If cleanup is done via Django admin or ORM delete, the file remains on the filesystem indefinitely. Over time, "deleted" files accumulate and consume storage.
**Trigger:** Deleting a StoredFile record via Django admin.
**Fix:** Add a `post_delete` signal that removes the file from disk using `instance.file.delete(save=False)`.

---

## EC-78: No File Path Traversal Protection in Upload
**File:** `core/storage/models/stored_file.py:12`
**Risk:** High — Path traversal
**Description:** Django's `FileField` uses `upload_to="storage/"` which is a relative path. While Django's `Storage.save()` does prevent path traversal by default on most backends, if a custom storage backend is used in the future or if the file's `name` attribute is manipulated before saving, an attacker could write files to arbitrary locations on the filesystem (e.g., `../../etc/cron.d/malicious`).
**Trigger:** Manipulated filename containing `../` sequences.
**Fix:** Sanitize filenames explicitly by stripping directory separators and using `os.path.basename()`.

---

## EC-79: No Quota Enforcement on Storage Uploads
**File:** `core/storage/services/storage_service.py`
**Risk:** Low — Storage exhaustion
**Description:** There is no per-user or per-entity storage quota. A user could upload files until the disk is full. The `quota_bytes` field exists on `Mailbox` but is not checked during file uploads. This could lead to disk full scenarios affecting mail delivery.
**Trigger:** User uploads files until disk is full.
**Fix:** Check available quota (or disk space) before accepting uploads. Reject uploads when disk usage exceeds 90%.

---

## EC-80: EntityType Enum Hardcoded — Not Extensible Without Code Change
**File:** `core/types/enums.py`
**Risk:** Low — Coupling
**Description:** `EntityType` has hardcoded values: PRODUCT, USER, MESSAGE, DOCUMENT. Adding a new entity type requires modifying the enum definition and creating a database migration. There is no dynamic registration mechanism for entity types.
**Trigger:** New app needs to associate files with its own entity type.
**Fix:** Consider a registry pattern where apps register their entity types, or use a string-based entity type with a configuration-based validation set.

---

## EC-81: No Background File Processing (Virus Scanning, Thumbnail Generation)
**File:** Not implemented
**Risk:** Medium — Malware distribution
**Description:** Uploaded files are stored as-is with no virus scanning or malware detection. If the platform allows file sharing via email attachments (which it does, via Postfix), an attacker could distribute malware through the system. There is no ClamAV integration or similar antivirus scanning step.
**Trigger:** Malicious file uploaded and sent as email attachment.
**Fix:** Integrate ClamAV scanning as an async Celery task triggered by file upload, with quarantine for infected files.
**Fix:** Integrate ClamAV scanning as an async Celery task triggered by file upload, with quarantine for infected files.
