#!/bin/sh
set -e

echo "=== ifinmail entrypoint ==="

# Wait for PostgreSQL to be ready (max 30 attempts = 60s)
echo "Waiting for PostgreSQL..."
MAX_ATTEMPTS=30
ATTEMPT=0
until python - <<'PY' 2>/dev/null
import os
import psycopg

psycopg.connect(
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=os.environ.get("DB_PORT", "5432"),
).close()
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
echo "  PostgreSQL is ready."

# Run Django checks
python manage.py check --deploy

# Apply database migrations
echo "Running migrations..."
if ! python manage.py migrate --noinput; then
    echo "ERROR: Database migration failed"
    exit 1
fi

# Create superuser if it doesn't exist (idempotent)
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "Ensuring superuser '${DJANGO_SUPERUSER_USERNAME}' exists..."
    python manage.py createsuperuser --noinput 2>/dev/null || true
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Ensure nginx (nobody user) can read static files from shared volume
chown -R nobody:nogroup /app/staticfiles 2>/dev/null || true
chmod -R 755 /app/staticfiles

echo "=== Starting ifinmail ==="
exec "$@"
