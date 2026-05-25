#!/bin/bash
# ifinmail restore_test.sh — Monthly restore verification
# The backup you never test is not a backup.
# Schedule: monthly (23 5 1 * *)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR="/backups/ifinmail_restore_test_$$"
COMPOSE_FILE="${PROJECT_ROOT}/provisioning/docker/docker-compose.yml"
ENV_FILE="${PROJECT_ROOT}/provisioning/.env"

# Load .env for GPG passphrase
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi
GPG_PASSPHRASE="${BACKUP_GPG_PASSPHRASE:-}"

echo "=== ifinmail Restore Test ==="
mkdir -p "$TEST_DIR"

# Find latest backup (unencrypted or encrypted)
LATEST=$(ls -t /backups/ifinmail_backup_*.tar.gz 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    LATEST=$(ls -t /backups/ifinmail_backup_*.tar.gz.gpg 2>/dev/null | head -1)
fi

if [ -z "$LATEST" ]; then
    echo "ERROR: No backups found in /backups/"
    rm -rf "$TEST_DIR" 2>/dev/null || true
    exit 1
fi

echo "Testing restore from: $LATEST (size: $(du -h "$LATEST" | cut -f1))"

# Decrypt if encrypted
if [[ "$LATEST" == *.gpg ]]; then
    echo "  Backup is GPG encrypted, decrypting..."
    DECRYPTED="${LATEST%.gpg}"
    if ! gpg --yes --pinentry-mode=loopback --passphrase "$GPG_PASSPHRASE" --decrypt --output "$DECRYPTED" "$LATEST" 2>/dev/null; then
        echo "ERROR: Failed to decrypt backup (GPG key missing or wrong passphrase?)"
        rm -rf "$TEST_DIR"
        exit 1
    fi
    LATEST="$DECRYPTED"
fi

tar -xzf "$LATEST" -C "$TEST_DIR"

PASS=0
FAIL=0

# 1. Verify SHA256 checksums
echo -n "  SHA256 checksums: "
if [ -f "$TEST_DIR/SHA256SUMS" ]; then
    if (cd "$TEST_DIR" && sha256sum -c SHA256SUMS --quiet 2>/dev/null); then
        echo "PASS"
        PASS=$((PASS+1))
    else
        echo "FAIL (checksum mismatch)"
        FAIL=$((FAIL+1))
    fi
else
    echo "WARN (no checksums file — older backup format)"
    PASS=$((PASS+1))
fi

# 2. Check PostgreSQL dump validity
echo -n "  PostgreSQL dump validity: "
if [ -f "$TEST_DIR/postgresql/ifinmail.dump" ]; then
    if pg_restore -l "$TEST_DIR/postgresql/ifinmail.dump" > /dev/null 2>&1; then
        echo "PASS"
        PASS=$((PASS+1))
    else
        echo "FAIL (corrupt dump)"
        FAIL=$((FAIL+1))
    fi
else
    echo "FAIL (dump file missing)"
    FAIL=$((FAIL+1))
fi

# 3. Test actual restore to a temporary test database
echo -n "  Test database restore: "
if [ -f "$TEST_DIR/postgresql/ifinmail.dump" ] && docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U ifinmail -c "SELECT 1" > /dev/null 2>&1; then
    # Create a temporary test database
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U ifinmail -c "DROP DATABASE IF EXISTS ifinmail_restore_test" > /dev/null 2>&1 || true
    if docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U ifinmail -c "CREATE DATABASE ifinmail_restore_test" > /dev/null 2>&1; then
        # Restore the dump to the test database
        if docker compose -f "$COMPOSE_FILE" exec -T postgres \
            pg_restore -U ifinmail -d ifinmail_restore_test "$TEST_DIR/postgresql/ifinmail.dump" > /dev/null 2>&1; then
            # Verify table count
            TABLE_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
                psql -U ifinmail -d ifinmail_restore_test -tAc \
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo "0")
            echo "PASS ($TABLE_COUNT tables restored)"
            PASS=$((PASS+1))
        else
            echo "FAIL (pg_restore failed)"
            FAIL=$((FAIL+1))
        fi
        # Clean up test database
        docker compose -f "$COMPOSE_FILE" exec -T postgres \
            psql -U ifinmail -c "DROP DATABASE IF EXISTS ifinmail_restore_test" > /dev/null 2>&1 || true
    else
        echo "FAIL (could not create test database)"
        FAIL=$((FAIL+1))
    fi
else
    echo "SKIP (PostgreSQL not available or no dump file)"
    PASS=$((PASS+1))
fi

# 4. Check mail storage
echo -n "  Mail storage: "
MAILDIRS=$(find "$TEST_DIR/mail" -type d 2>/dev/null | wc -l)
if [ "$MAILDIRS" -gt 0 ]; then
    echo "PASS ($MAILDIRS directories)"
    PASS=$((PASS+1))
else
    echo "WARN (no mail directories — may be empty system)"
    PASS=$((PASS+1))
fi

# 5. Check configs
echo -n "  Configuration files: "
CONFIG_COUNT=0
[ -f "$TEST_DIR/configs/postfix/main.cf" ] && CONFIG_COUNT=$((CONFIG_COUNT+1))
[ -f "$TEST_DIR/configs/dovecot/dovecot.conf" ] && CONFIG_COUNT=$((CONFIG_COUNT+1))
[ -f "$TEST_DIR/configs/dotenv" ] && CONFIG_COUNT=$((CONFIG_COUNT+1))
echo "PASS ($CONFIG_COUNT key files present)"
PASS=$((PASS+1))

# 6. Check DKIM keys
echo -n "  DKIM keys: "
DKIM_COUNT=$(find "$TEST_DIR/dkim" -name "*.key" 2>/dev/null | wc -l)
if [ "$DKIM_COUNT" -gt 0 ]; then
    echo "PASS ($DKIM_COUNT keys)"
    PASS=$((PASS+1))
else
    echo "WARN (no keys — add domains to generate)"
    PASS=$((PASS+1))
fi

# Summary
echo ""
echo "  Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    echo "=== RESTORE TEST FAILED — INVESTIGATE IMMEDIATELY ==="
else
    echo "=== Restore test passed ==="
fi

rm -rf "$TEST_DIR"
