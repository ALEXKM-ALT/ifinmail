#!/bin/sh
set -e

# Substitute environment variables in pgsql config files
for f in /etc/postfix/pgsql/*.cf; do
    if [ -f "$f" ]; then
        sed -i "s/\${IFINMAIL_DB_PASSWORD}/${IFINMAIL_DB_PASSWORD:-ifinmail_dev}/g" "$f"
    fi
done

# Generate TLS cert if not present
if [ ! -f /etc/ssl/certs/postfix.pem ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/ssl/private/postfix.key \
        -out /etc/ssl/certs/postfix.pem \
        -subj "/C=US/ST=State/L=City/O=ifinmail/CN=mail.ifinmail.local" 2>/dev/null
fi

exec "$@"
