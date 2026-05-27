# Backup & Disaster Recovery — Edge Cases (92–100)

## EC-92: GPG Key for Backup Encryption Not Backed Up Separately
**File:** `provision.sh:ensure_backup_gpg_key`
**Risk:** Critical — Backup data loss
**Description:** The GPG key used to encrypt backups is generated on the server and stored only in the local GPG keyring. If the server crashes, the GPG private key is lost, making ALL encrypted backups permanently unrecoverable. The backup itself contains encrypted data that cannot be decrypted without the key.
**Trigger:** Server loss (catastrophic failure, data center fire, disk failure).
**Fix:** Export the GPG private key, encrypt it with a strong passphrase, and include it in the backup itself (in a separate, non-encrypted manifest), or output it to the admin during provisioning with instructions to store it offline.

---

## EC-93: Backup Script Hardcodes Docker Compose Exec User — May Fail on Permission
**File:** `backup_full.sh:42-47`
**Risk:** Medium — Backup failure
**Description:** The backup script runs `docker compose exec -T postgres pg_dump -U ifinmail ...` from the host machine. If the docker compose context is not available on the host (e.g., running as a different user, or the socket permissions differ), the `docker compose exec` command fails silently because stderr is redirected to `/dev/null`.
**Trigger:** Running backup script as non-root user without docker group access.
**Fix:** Check for `docker compose exec` access before running and provide a clear error message instead of redirecting stderr to `/dev/null`.

---

## EC-94: Backup Integrity Verification Does Not Fail on Mismatch
**File:** `backup_full.sh:160-166`
**Risk:** Medium — Silent corruption
**Description:** After verifying checksums, the script prints "PASS" or "FAIL" but does not exit with a non-zero code on failure. The backup cron job runs daily and reports success even if the verification fails. Silent corruption propagates unchecked.
**Trigger:** File corruption during backup creation (I/O error, disk full).
**Fix:** Add `exit 1` after the FAIL message in verification, so the backup script alerts the monitoring system.

---

## EC-95: Restore Test Can Modify Production Database State
**File:** `restore_test.sh:90-93`
**Risk:** Low — Side effects
**Description:** The restore test creates a temporary test database (`ifinmail_restore_test`) and drops it when done. However, it uses `DROP DATABASE IF EXISTS ifinmail_restore_test` before creation, which could accidentally drop the test database from a previous, still-running test. More critically, if a production database name matches the pattern (unlikely but possible), it could be affected.
**Trigger:** Concurrent restore test executions.
**Fix:** Use a truly random database name suffix (e.g., `ifinmail_restore_test_$$_{RANDOM}`) to avoid collisions.

---

## EC-96: Backup Does Not Include Django Migrations State
**File:** `backup_full.sh`
**Risk:** Medium — Inconsistent restore
**Description:** The backup includes the PostgreSQL dump (schema + data) but does not track the Django migration state. If a restore is performed against a newer version of the application that expects additional/migrated tables, the database schema will be outdated and migrations may fail or produce conflicts.
**Trigger:** Restoring an old backup onto a newer version of the application.
**Fix:** Include the Django migration table contents (`django_migrations` table, which is part of the pg_dump) and verify migration state against the application code during restore.

---

## EC-97: No Backup of Redis Data (Sessions, Cache, Celery State)
**File:** `backup_full.sh`
**Risk:** Medium — Loss of transient data
**Description:** The backup script backs up PostgreSQL, mail storage, DKIM keys, TLS certs, and configs. It does NOT back up Redis data (which stores Django sessions, cache entries, and potentially Celery task results). After a full restore, all sessions are invalidated (forcing re-login), and cached data is lost.
**Trigger:** Full disaster recovery after server loss.
**Fix:** Add a Redis backup step: `docker compose exec -T redis redis-cli --rdb /tmp/dump.rdb` and include it in the backup archive.

---

## EC-98: Backup Retention Uses `mtime` — May Delete Wrong Files
**File:** `backup_full.sh:152`
**Risk:** Low — Premature deletion
**Description:** The cleanup command uses `-mtime +$RETENTION_DAYS` which matches files by modification time, not creation time. If a backup file is touched (e.g., for verification or copying), its `mtime` updates, making it appear newer than it is. Conversely, old log files with the same name pattern could be incorrectly matched.
**Trigger:** Touching a backup file changes its mtime; log files matching the pattern.
**Fix:** Use a stricter glob pattern (`ifinmail_backup_*.tar.gz*`) and consider using `-ctime` (creation time) or basename-based date parsing.

---

## EC-99: No Maildir Locking During Backup — Inconsistent State
**File:** `backup_full.sh:57-63`
**Risk:** Medium — Incomplete mail backup
**Description:** Mail storage is backed up by copying the Docker volume while the mail system is running. Postfix and Dovecot may be writing to Maildirs concurrently, resulting in a backup that contains partially-written files, missing files created during the backup, or inconsistent directory state. The `cp -a` command warns but continues on error.
**Trigger:** Email delivery during backup window.
**Fix:** Flush mail queues before backup, use filesystem snapshots, or quiesce Dovecot (doveadm kick) before copying.

---

## EC-100: No Backup of fail2ban State or iptables Rules
**File:** `backup_full.sh`
**Risk:** Low — Fail2ban state loss
**Description:** fail2ban bans are stored in memory and iptables rules are ephemeral. After a server restart, all fail2ban ban information is lost. An attacker who was previously banned can immediately resume attacks. The backup does not include `/var/lib/fail2ban/` or iptables rules persistence.
**Trigger:** Server restart after fail2ban has banned IPs.
**Fix:** Back up fail2ban's database (`/var/lib/fail2ban/fail2ban.sqlite3`) and add iptables-persistent or `iptables-save` to the restore procedure.
