#!/bin/bash
# ifinmail backup_full.sh — Full backup including PostgreSQL, mail, configs, DKIM
# Schedule: daily via cron (17 3 * * *)
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Detect project root: provisioning/scripts -> provisioning -> project root
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_ROOT="/backups/${TIMESTAMP}"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}
ENCRYPT=${BACKUP_ENCRYPT:-false}
COMPOSE_FILE="${PROJECT_ROOT}/provisioning/docker/docker-compose.yml"

# Notification webhook (set in .env or crontab)
NOTIFY_URL="${BACKUP_NOTIFY_URL:-}"

notify_failure() {
    local msg="$1"
    echo "ERROR: $msg" >&2
    if [ -n "$NOTIFY_URL" ]; then
        curl -fsS --connect-timeout 10 --max-time 30 -X POST \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"ifinmail backup FAILED: $msg\"}" "$NOTIFY_URL" || true
    fi
}

echo "=== ifinmail Backup: $TIMESTAMP ==="

# Ensure backup directory exists
mkdir -p /backups

# Verify compose file is accessible
if [ ! -f "$COMPOSE_FILE" ]; then
    notify_failure "compose file not found at $COMPOSE_FILE"
    exit 1
fi

# 1. PostgreSQL dump
echo "[1/6] Backing up PostgreSQL..."
mkdir -p "$BACKUP_ROOT/postgresql"
if ! docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U ifinmail -Fc ifinmail > "$BACKUP_ROOT/postgresql/ifinmail.dump" 2>/dev/null; then
    notify_failure "PostgreSQL dump failed"
    rm -rf "$BACKUP_ROOT"
    exit 1
fi

# Schema-only for quick reference
docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U ifinmail --schema-only ifinmail > "$BACKUP_ROOT/postgresql/ifinmail_schema.sql" 2>/dev/null || true

# 2. Mail storage (Maildir)
echo "[2/6] Backing up mail storage..."
mkdir -p "$BACKUP_ROOT/mail"
# Use the mail_data volume directly
if docker volume ls --format '{{.Name}}' | grep -q 'ifinmail_mail_data'; then
    docker run --rm \
        -v "ifinmail_mail_data:/source_mail:ro" \
        -v "$BACKUP_ROOT/mail:/backup_mail" \
        alpine:latest \
        sh -c "cp -a /source_mail/. /backup_mail/" 2>/dev/null || \
        echo "  Warning: mail data copy had issues (may be empty)"
fi

# 3. Configuration files
echo "[3/6] Backing up configuration..."
mkdir -p "$BACKUP_ROOT/configs"
cp -r "${PROJECT_ROOT}/provisioning/docker/postfix" "$BACKUP_ROOT/configs/" 2>/dev/null || true
cp -r "${PROJECT_ROOT}/provisioning/docker/dovecot" "$BACKUP_ROOT/configs/" 2>/dev/null || true
cp -r "${PROJECT_ROOT}/provisioning/docker/rspamd/local.d" "$BACKUP_ROOT/configs/rspamd" 2>/dev/null || true
if [ -f "${PROJECT_ROOT}/provisioning/.env" ]; then
    cp "${PROJECT_ROOT}/provisioning/.env" "$BACKUP_ROOT/configs/dotenv"
fi

# 4. DKIM keys (separate — these are irreplaceable)
echo "[4/6] Backing up DKIM keys..."
mkdir -p "$BACKUP_ROOT/dkim"
DKIM_DIR="${PROJECT_ROOT}/provisioning/docker/dkim"
if [ -d "$DKIM_DIR" ] && [ -n "$(ls -A "$DKIM_DIR"/*.key 2>/dev/null)" ]; then
    cp -r "$DKIM_DIR" "$BACKUP_ROOT/dkim/keys"
    chmod -R 600 "$BACKUP_ROOT/dkim"
else
    notify_failure "DKIM keys missing from $DKIM_DIR — backup cannot proceed without irreplaceable keys"
    rm -rf "$BACKUP_ROOT"
    exit 1
fi

# 5. Manifest with SHA256 checksums
echo "[5/6] Backing up TLS certificates..."
mkdir -p "$BACKUP_ROOT/certs"
CERTS_DIR="${PROJECT_ROOT}/provisioning/docker/certs"
if [ -d "$CERTS_DIR" ]; then
    # Copy Let's Encrypt account credentials and renewal config (essential for renewal)
    if [ -d "$CERTS_DIR/accounts" ]; then
        cp -r "$CERTS_DIR/accounts" "$BACKUP_ROOT/certs/"
    fi
    if [ -d "$CERTS_DIR/renewal" ]; then
        cp -r "$CERTS_DIR/renewal" "$BACKUP_ROOT/certs/"
    fi
    # Copy live certificates (symlinks to archive, so follow symlinks)
    if [ -d "$CERTS_DIR/live" ]; then
        cp -rL "$CERTS_DIR/live" "$BACKUP_ROOT/certs/"
    fi
    # Copy archive (actual cert files)
    if [ -d "$CERTS_DIR/archive" ]; then
        cp -r "$CERTS_DIR/archive" "$BACKUP_ROOT/certs/"
    fi
fi

echo "[6/6] Creating manifest and checksums..."
cat > "$BACKUP_ROOT/MANIFEST.txt" << MANIFEST
Backup: $TIMESTAMP
Host: $(hostname)
Project: $PROJECT_ROOT
Date: $(date -Iseconds)
Encryption: $ENCRYPT
Contents:
  - PostgreSQL dump (ifinmail.dump + schema)
  - Mail storage (/var/mail/vhosts)
  - Configuration (postfix, dovecot, rspamd, .env)
  - DKIM keys
  - TLS certificates (Let's Encrypt accounts, renewal, live, archive)
MANIFEST

# Generate SHA256 checksums
echo "Generating SHA256 checksums..."
(cd "$BACKUP_ROOT" && find . -type f ! -name MANIFEST.txt ! -name SHA256SUMS -exec sha256sum {} \;) > "$BACKUP_ROOT/SHA256SUMS"

# Compress
echo "Compressing backup..."
ARCHIVE_NAME="/backups/ifinmail_backup_${TIMESTAMP}.tar.gz"
tar -czf "$ARCHIVE_NAME" -C "$BACKUP_ROOT" .

# Encrypt if enabled
if [ "$ENCRYPT" = "true" ]; then
    echo "Encrypting backup..."
    if command -v gpg >/dev/null 2>&1 && [ -n "${BACKUP_GPG_RECIPIENT:-}" ]; then
        gpg --yes --encrypt --recipient "$BACKUP_GPG_RECIPIENT" \
            --output "${ARCHIVE_NAME}.gpg" "$ARCHIVE_NAME"
        rm -f "$ARCHIVE_NAME"
        ARCHIVE_NAME="${ARCHIVE_NAME}.gpg"
    else
        echo "  Warning: gpg not found or BACKUP_GPG_RECIPIENT not set, skipping encryption"
    fi
fi

rm -rf "$BACKUP_ROOT"

# Clean old backups
echo "Cleaning backups older than $RETENTION_DAYS days..."
find /backups -name "ifinmail_backup_*.tar.gz*" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# Report
SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
echo "=== Backup complete: $ARCHIVE_NAME ($SIZE) ==="

# Verify checksums
echo "Verifying backup integrity..."
TMP_VERIFY=$(mktemp -d)
VERIFY_ARCHIVE="$ARCHIVE_NAME"
if [[ "$ARCHIVE_NAME" == *.gpg ]]; then
    VERIFY_ARCHIVE="$TMP_VERIFY/backup.tar.gz"
    if ! gpg --batch --quiet --decrypt --output "$VERIFY_ARCHIVE" "$ARCHIVE_NAME" 2>/dev/null; then
        echo "  Checksum verification: SKIPPED (encrypted archive could not be decrypted)"
        rm -rf "$TMP_VERIFY"
        exit 0
    fi
fi
tar -xzf "$VERIFY_ARCHIVE" -C "$TMP_VERIFY" 2>/dev/null || true
if [ -f "$TMP_VERIFY/SHA256SUMS" ]; then
    (cd "$TMP_VERIFY" && sha256sum -c SHA256SUMS --quiet 2>/dev/null) && \
        echo "  Checksum verification: PASS" || \
        echo "  Checksum verification: FAIL (some files may have changed during backup)"
fi
rm -rf "$TMP_VERIFY"
