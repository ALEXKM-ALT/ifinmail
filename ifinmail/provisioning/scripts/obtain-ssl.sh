#!/bin/bash
# ifinmail obtain-ssl.sh — Obtain TLS certificates via Certbot/ACME
# Requires: Docker stack running, DOMAIN set in .env
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROVISIONING_DIR="$(dirname "$SCRIPT_DIR")"

if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose --env-file "$PROVISIONING_DIR/.env" -f "$PROVISIONING_DIR/docker/docker-compose.yml")
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose --env-file "$PROVISIONING_DIR/.env" -f "$PROVISIONING_DIR/docker/docker-compose.yml")
else
    echo "ERROR: docker compose v2 or docker-compose v1 is required."
    exit 1
fi

# Load environment
set -a
source "$PROVISIONING_DIR/.env"
set +a

DOMAIN="${DOMAIN:?DOMAIN must be set in .env}"
MAIL_HOSTNAME="${MAIL_HOSTNAME:-mail.$DOMAIN}"
EMAIL="${ADMIN_EMAIL:-admin@$DOMAIN}"
CERTBOT_WWW="$PROVISIONING_DIR/docker/nginx/www"
CERTBOT_CERTS="$PROVISIONING_DIR/docker/certs"
LIVE_DIR="$CERTBOT_CERTS/live/$MAIL_HOSTNAME"

echo "Obtaining TLS certificate for: $DOMAIN"
echo "Mail hostname: $MAIL_HOSTNAME"
echo "Contact email: $EMAIL"

# Ensure nginx is serving ACME challenges
echo "Ensuring nginx is running for ACME challenges..."
"${COMPOSE[@]}" up -d nginx 2>/dev/null || true
sleep 2

ISSUER="$(openssl x509 -in "$LIVE_DIR/fullchain.pem" -noout -issuer 2>/dev/null || true)"
BACKUP_DIR=""
if [ -n "$ISSUER" ] && [[ "$ISSUER" != *"Let's Encrypt"* ]]; then
    echo "Backing up self-signed certificate before requesting Let's Encrypt..."
    BACKUP_DIR="$(mktemp -d)"
    cp -a "$LIVE_DIR" "$BACKUP_DIR/" 2>/dev/null || true
    rm -rf "$LIVE_DIR" "$CERTBOT_CERTS/archive/$MAIL_HOSTNAME" "$CERTBOT_CERTS/renewal/$MAIL_HOSTNAME.conf"
fi

# Obtain certificate via webroot using the containerized certbot service
echo "Running certbot via compose..."
if "${COMPOSE[@]}" run --rm certbot \
    certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --non-interactive \
    --agree-tos \
    --cert-name "$MAIL_HOSTNAME" \
    -m "$EMAIL" \
    -d "$MAIL_HOSTNAME" \
    -d "$DOMAIN" \
    -d "mta-sts.$DOMAIN"; then
    # Clean up self-signed backup on success
    rm -rf "$BACKUP_DIR" 2>/dev/null || true
    if [ ! -s "$LIVE_DIR/dh.pem" ]; then
        openssl dhparam -out "$LIVE_DIR/dh.pem" 2048
    fi
    echo "Certificate obtained successfully!"
    echo "Certificate stored at: $LIVE_DIR/"

    # Restart nginx to pick up new cert
    "${COMPOSE[@]}" restart nginx

    echo ""
    echo "Auto-renewal is handled by the certbot service:"
    echo "  docker compose --profile certbot up -d certbot"
else
    # Restore self-signed cert on failure
    if [ -n "${BACKUP_DIR:-}" ] && [ -d "$BACKUP_DIR" ]; then
        local_live="$(basename "$LIVE_DIR")"
        mkdir -p "$LIVE_DIR"
        cp -a "$BACKUP_DIR/$local_live/"* "$LIVE_DIR/" 2>/dev/null || true
        rm -rf "$BACKUP_DIR" 2>/dev/null || true
        echo "Restored self-signed certificate."
    fi
    echo "ERROR: Certificate issuance failed."
    echo "Check that:"
    echo "  1. DNS for $DOMAIN points to this server"
    echo "  2. Port 80 is open and accessible"
    echo "  3. Nginx is running and serving ACME challenges"
    exit 1
fi
