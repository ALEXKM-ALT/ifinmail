#!/bin/sh
set -e

# Substitute DB password in SQL config
if [ -f /etc/dovecot/conf.d/dovecot-sql.conf.ext ]; then
    sed -i "s/\${IFINMAIL_DB_PASSWORD}/${IFINMAIL_DB_PASSWORD:-ifinmail_dev}/g" \
        /etc/dovecot/conf.d/dovecot-sql.conf.ext
fi

# Generate self-signed TLS cert if missing
if [ ! -f /etc/dovecot/private/dovecot.pem ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/dovecot/private/dovecot.key \
        -out /etc/dovecot/private/dovecot.pem \
        -subj "/C=US/ST=State/L=City/O=ifinmail/CN=mail.ifinmail.local" 2>/dev/null

    openssl dhparam -out /etc/dovecot/private/dh.pem 2048 2>/dev/null
fi

exec dovecot -F
