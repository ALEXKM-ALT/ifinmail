#!/usr/bin/env sh
set -eu

sed_escape() {
    printf "%s" "$1" | sed 's/[|&]/\\&/g'
}

DOVECOT_DB_PASSWORD="${DOVECOT_DB_PASSWORD:?DOVECOT_DB_PASSWORD is required}"

DOVECOT_DB_PASSWORD_ESC="$(sed_escape "$DOVECOT_DB_PASSWORD")"
sed "s|__DOVECOT_DB_PASSWORD__|$DOVECOT_DB_PASSWORD_ESC|g" \
    /etc/dovecot/dovecot-sql.conf.ext.template > /etc/dovecot/dovecot-sql.conf.ext
chown root:dovecot /etc/dovecot/dovecot-sql.conf.ext
chmod 640 /etc/dovecot/dovecot-sql.conf.ext

exec "$@"
