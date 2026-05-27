#!/usr/bin/env bash
set -eu

sed_escape() {
    printf "%s" "$1" | sed 's/[|&]/\\&/g'
}

: "${MAIL_HOSTNAME:?MAIL_HOSTNAME is required}"
: "${MAIL_DOMAIN:?MAIL_DOMAIN is required}"
POSTFIX_DB_PASSWORD="${POSTFIX_DB_PASSWORD:?POSTFIX_DB_PASSWORD is required}"

MAIL_HOSTNAME_ESC="$(sed_escape "$MAIL_HOSTNAME")"
MAIL_DOMAIN_ESC="$(sed_escape "$MAIL_DOMAIN")"
POSTFIX_DB_PASSWORD_ESC="$(sed_escape "$POSTFIX_DB_PASSWORD")"

sed \
    -e "s|__MAIL_HOSTNAME__|$MAIL_HOSTNAME_ESC|g" \
    -e "s|__MAIL_DOMAIN__|$MAIL_DOMAIN_ESC|g" \
    /etc/postfix/main.cf.template > /etc/postfix/main.cf

for template in /etc/postfix/pgsql-templates/*.cf; do
    map="/etc/postfix/pgsql/$(basename "$template")"
    sed "s|__POSTFIX_DB_PASSWORD__|$POSTFIX_DB_PASSWORD_ESC|g" "$template" > "$map"
    chown root:postfix "$map"
    chmod 640 "$map"
done

mkdir -p /var/spool/postfix /var/mail/vhosts
if command -v postfix >/dev/null 2>&1; then
    postfix set-permissions >/dev/null 2>&1 || true
fi
for root_owned_dir in \
    /var/spool/postfix/etc \
    /var/spool/postfix/lib \
    /var/spool/postfix/usr \
    /var/spool/postfix/usr/lib \
    /var/spool/postfix/usr/lib/sasl2 \
    /var/spool/postfix/usr/lib/zoneinfo
do
    [ -d "$root_owned_dir" ] && chown root:root "$root_owned_dir"
done

# Wait for PostgreSQL to accept connections
echo "Waiting for PostgreSQL readiness..."
for i in $(seq 1 30); do
    if timeout 3 bash -c "echo > /dev/tcp/postgres/5432" 2>/dev/null; then
        echo "PostgreSQL is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: PostgreSQL not ready after 30 attempts. Starting anyway..."
    else
        sleep 2
    fi
done

exec "$@"
