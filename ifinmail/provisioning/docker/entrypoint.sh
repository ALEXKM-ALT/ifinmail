#!/bin/sh
set -e

echo "=== ifinmail entrypoint ==="

run_as_app() {
    if [ "$(id -u)" = "0" ]; then
        su app -s /bin/sh -c 'exec "$@"' -- sh "$@"
    else
        "$@"
    fi
}

# Wait for PostgreSQL to be ready AND init-db.sh to complete (max 60 attempts = 120s)
echo "Waiting for PostgreSQL..."
MAX_ATTEMPTS=60
ATTEMPT=0
until python - <<'PY' 2>/dev/null
import os
import psycopg

conn = psycopg.connect(
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=os.environ.get("DB_PORT", "5432"),
)
cur = conn.cursor()
# EC-30: Verify init-db.sh has completed by checking for core tables
cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'domains')")
ready = cur.fetchone()[0]
cur.close()
conn.close()
if not ready:
    exit(1)
PY
do
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: PostgreSQL did not become ready after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    echo "  PostgreSQL not ready, retrying in 2s... (attempt $ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
done
echo "  PostgreSQL is ready (init-db.sh complete)."

# Run Django checks
run_as_app python manage.py check --deploy

# Apply database migrations
echo "Running migrations..."
if ! run_as_app python manage.py migrate --noinput; then
    echo "ERROR: Database migration failed"
    exit 1
fi

# Create superuser if it doesn't exist (idempotent)
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    # EC-02: Validate password is non-empty and has minimum length
    PASSWORD_LEN=${#DJANGO_SUPERUSER_PASSWORD}
    if [ "$PASSWORD_LEN" -lt 8 ]; then
        echo "ERROR: DJANGO_SUPERUSER_PASSWORD must be at least 8 characters (got $PASSWORD_LEN)"
        exit 1
    fi
    echo "Ensuring superuser '${DJANGO_SUPERUSER_USERNAME}' exists..."
    run_as_app python manage.py createsuperuser --noinput 2>/dev/null || true
else
    echo "WARNING: DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set — no superuser created."
fi

# Collect static files
echo "Collecting static files..."
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /app/staticfiles
fi
run_as_app python manage.py collectstatic --noinput --clear

# Compile translation files for i18n
echo "Compiling translations..."
run_as_app python manage.py compilemessages

# EC-101: Restrict permissions on static files — world-readable, not executable
chmod -R 644 /app/staticfiles
find /app/staticfiles -type d -exec chmod 755 {} \;

echo "=== Starting ifinmail ==="
if [ "$(id -u)" = "0" ]; then
    exec su app -s /bin/sh -c 'exec "$@"' -- sh "$@"
else
    exec "$@"
fi
