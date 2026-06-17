#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Wait for API server to be up (max 10 seconds)
if [ "${ELECTRON_DEV:-1}" = "1" ]; then
  echo "Checking API server..."
  for i in $(seq 1 10); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
      echo "API server is running."
      break
    fi
    if [ "$i" -eq 10 ]; then
      echo "Warning: API server not reachable at http://localhost:8000"
      echo "Start it with: cd .. && PYTHONPATH=src python3 -m uvicorn ifinmail.api.app:app --host 0.0.0.0 --port 8000"
    fi
    sleep 1
  done
fi

if [ ! -d node_modules ]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Starting ifinmail Desktop..."
exec npx electron . --no-sandbox "$@"
