#!/usr/bin/env sh
set -eu

sed_escape() {
    printf "%s" "$1" | sed 's/[|&]/\\&/g'
}

DOVECOT_DB_PASSWORD="${DOVECOT_DB_PASSWORD:?DOVECOT_DB_PASSWORD is required}"
PGSSLMODE="${PGSSLMODE:-prefer}"

DOVECOT_DB_PASSWORD_ESC="$(sed_escape "$DOVECOT_DB_PASSWORD")"
PGSSLMODE_ESC="$(sed_escape "$PGSSLMODE")"
sed \
    -e "s|__DOVECOT_DB_PASSWORD__|$DOVECOT_DB_PASSWORD_ESC|g" \
    -e "s|__PGSSLMODE__|$PGSSLMODE_ESC|g" \
    /etc/dovecot/dovecot-sql.conf.ext.template > /etc/dovecot/dovecot-sql.conf.ext
chown root:dovecot /etc/dovecot/dovecot-sql.conf.ext
chmod 640 /etc/dovecot/dovecot-sql.conf.ext

exec "$@"
