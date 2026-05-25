#!/bin/sh
# certbot deploy hook — reload services after successful certificate renewal
set -e

echo "Certbot deploy hook: certificate renewed, restarting services..."

COMPOSE_FILE="${COMPOSE_FILE:-/config/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-/config/.env}"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart nginx postfix dovecot postgres 2>/dev/null || {
    echo "WARNING: Could not restart services via docker compose."
    echo "Run 'make reload' manually to pick up the new certificate."
}

echo "  Services restarted."
