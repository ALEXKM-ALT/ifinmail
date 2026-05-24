#!/bin/bash
# ifinmail obtain-ssl.sh — Obtain TLS certificates via Certbot/ACME
# Requires: Docker stack running, DOMAIN set in .env
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROVISIONING_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment
set -a
source "$PROVISIONING_DIR/.env"
set +a

DOMAIN="${DOMAIN:?DOMAIN must be set in .env}"
MAIL_HOSTNAME="${MAIL_HOSTNAME:-mail.$DOMAIN}"
EMAIL="${ADMIN_EMAIL:-admin@$DOMAIN}"
CERTBOT_WWW="$PROVISIONING_DIR/docker/nginx/www"
CERTBOT_CERTS="$PROVISIONING_DIR/docker/certs"

echo "Obtaining TLS certificate for: $DOMAIN"
echo "Mail hostname: $MAIL_HOSTNAME"
echo "Contact email: $EMAIL"

# Ensure nginx is serving ACME challenges
echo "Ensuring nginx is running for ACME challenges..."
docker compose --env-file "$PROVISIONING_DIR/.env" -f "$PROVISIONING_DIR/docker/docker-compose.yml" up -d nginx 2>/dev/null || true
sleep 2

# Obtain certificate via webroot
echo "Running certbot..."
docker run --rm \
    -v "$CERTBOT_WWW:/var/www/certbot" \
    -v "$CERTBOT_CERTS:/etc/letsencrypt" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --non-interactive \
    --agree-tos \
    -m "$EMAIL" \
    -d "$DOMAIN" \
    -d "$MAIL_HOSTNAME"

if [ $? -eq 0 ]; then
    echo "Certificate obtained successfully!"
    echo "Certificate stored at: $CERTBOT_CERTS/live/$MAIL_HOSTNAME/"

    # Restart nginx to pick up new cert
    docker compose --env-file "$PROVISIONING_DIR/.env" -f "$PROVISIONING_DIR/docker/docker-compose.yml" restart nginx

    echo ""
    echo "Auto-renewal (run via cron monthly):"
    echo "  docker run --rm -v $CERTBOT_WWW:/var/www/certbot -v $CERTBOT_CERTS:/etc/letsencrypt certbot/certbot renew"
else
    echo "ERROR: Certificate issuance failed."
    echo "Check that:"
    echo "  1. DNS for $DOMAIN points to this server"
    echo "  2. Port 80 is open and accessible"
    echo "  3. Nginx is running and serving ACME challenges"
    exit 1
fi
