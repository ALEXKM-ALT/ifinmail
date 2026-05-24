#!/bin/bash
# ifinmail deploy.sh — Full deployment automation
# Provisions a fresh VPS with the entire ifinmail stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROVISIONING_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROVISIONING_DIR/docker"

echo "======================================"
echo "  ifinmail Deployment"
echo "======================================"

# --- 1. Check prerequisites ---
echo "[1/7] Checking prerequisites..."
for cmd in docker openssl; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  ERROR: $cmd is required but not installed."
        exit 1
    fi
done

if ! docker compose version &>/dev/null; then
    echo "  ERROR: docker compose (v2) is required but not available."
    exit 1
fi
echo "  Prerequisites OK."

# --- 2. Environment setup ---
echo "[2/7] Setting up environment..."
if [ ! -f "$PROVISIONING_DIR/.env" ]; then
    if [ -f "$PROVISIONING_DIR/.env.example" ]; then
        cp "$PROVISIONING_DIR/.env.example" "$PROVISIONING_DIR/.env"
        echo "  Created .env from .env.example — edit it with your settings!"
        echo "  Required: DOMAIN, POSTGRES_ADMIN_PASSWORD, DOVECOT_DB_PASSWORD, POSTFIX_DB_PASSWORD, SECRET_KEY"
        read -rp "  Continue after editing .env? [y/N] " confirm
        if [ "${confirm,,}" != "y" ]; then
            echo "  Exiting. Edit $PROVISIONING_DIR/.env and re-run this script."
            exit 0
        fi
    else
        echo "  ERROR: No .env or .env.example found."
        exit 1
    fi
fi

# Source .env
set -a
source "$PROVISIONING_DIR/.env"
set +a

# Validate required environment variables
REQUIRED_VARS=(DOMAIN POSTGRES_ADMIN_PASSWORD DOVECOT_DB_PASSWORD POSTFIX_DB_PASSWORD SECRET_KEY)
MISSING=false
for var in "${REQUIRED_VARS[@]}"; do
    value="${!var:-}"
    if [ -z "$value" ] || [[ "$value" == change_me* ]] || [[ "$value" == dev_* ]]; then
        echo "  ERROR: Required environment variable $var is not set or uses a placeholder value."
        MISSING=true
    fi
 done
if [ "$MISSING" = true ]; then
    echo "  Exiting. Update $PROVISIONING_DIR/.env with real values."
    exit 1
fi

MAIL_DOMAIN="${MAIL_DOMAIN:-${DOMAIN}}"
MAIL_HOSTNAME="${MAIL_HOSTNAME:-mail.${DOMAIN}}"

# --- 3. Generate DKIM keys ---
echo "[3/7] Checking DKIM keys..."
SELECTOR="${DKIM_SELECTOR:-default}"
DOMAIN="${DOMAIN:-example.com}"
DKIM_KEY_PATH="$DOCKER_DIR/dkim/${SELECTOR}.${DOMAIN}.key"
DKIM_PUB_PATH="${DKIM_KEY_PATH%.key}.pub"
if [ ! -f "$DKIM_KEY_PATH" ]; then
    mkdir -p "$DOCKER_DIR/dkim"
    openssl genrsa -out "$DKIM_KEY_PATH" 2048
    openssl rsa -in "$DKIM_KEY_PATH" -pubout -out "$DKIM_PUB_PATH"
    chmod 600 "$DKIM_KEY_PATH"
    echo "  DKIM key pair generated for $SELECTOR._domainkey.$DOMAIN"
    echo ""
    echo "  === DNS RECORD TO ADD ==="
    echo "  Name:   $SELECTOR._domainkey.$DOMAIN"
    echo "  Type:   TXT"
    printf "  Value:  v=DKIM1; k=rsa; p="
    grep -v "^-" "$DKIM_PUB_PATH" | tr -d '\n'
    echo ""
    echo "  ========================"
    echo ""
else
    echo "  DKIM key pair already exists at $DKIM_KEY_PATH."
fi

# --- 4. Build images ---
echo "[4/7] Building Docker images..."
cd "$DOCKER_DIR"
docker compose --env-file "$PROVISIONING_DIR/.env" build --pull
echo "  Images built."

# --- 5. Start stack ---
echo "[5/7] Starting ifinmail stack..."
docker compose --env-file "$PROVISIONING_DIR/.env" up -d
echo "  Stack starting..."

# --- 6. Wait for healthy services ---
echo "[6/7] Waiting for services to be healthy..."
ATTEMPTS=0
MAX_ATTEMPTS=60
while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    UNHEALTHY=$(docker compose ps --format json 2>/dev/null | grep -v '"Health":"healthy"' | grep -v '"Health":""' | wc -l || echo 0)
    if [ "$UNHEALTHY" -eq 0 ]; then
        echo "  All services healthy!"
        break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    sleep 5
    echo "  Waiting... ($ATTEMPTS/$MAX_ATTEMPTS)"
done

if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
    echo "  WARNING: Some services may still be starting. Check with: docker compose ps"
fi

# --- 7. Display status ---
echo "[7/7] Deployment summary"
echo ""
docker compose ps
echo ""
echo "======================================"
echo "  ifinmail deployed!"
echo ""
echo "  API: https://${DOMAIN:-localhost}"
echo "  Postfix SMTP: ${DOMAIN:-localhost}:587 (submission)"
echo "  Dovecot IMAP: ${DOMAIN:-localhost}:993 (IMAPS)"
echo ""
echo "  Next steps:"
echo "    1. Run obtain-ssl.sh to get TLS certificates"
echo "    2. Add DNS records (SPF, DKIM, DMARC, MX)"
echo "    3. Set up cron for backup_full.sh"
echo "======================================"
