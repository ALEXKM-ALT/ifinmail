#!/bin/sh
# certbot auto-renewal entrypoint — runs certbot renew on a 12h loop
set -eu

RENEWAL_INTERVAL="${RENEWAL_INTERVAL:-12h}"

echo "=== ifinmail certbot auto-renewal ==="
echo "  Check interval: every $RENEWAL_INTERVAL"

while :; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): Running certbot renew..."
    certbot renew \
        --deploy-hook "/hooks/deploy-hook.sh" \
        --non-interactive \
        2>&1 || echo "  Renewal check complete (some failures are expected if certs aren't due yet)."
    echo "  Next check in $RENEWAL_INTERVAL."
    sleep "${RENEWAL_INTERVAL}"
done
