#!/bin/sh
set -eu

DB_HOST="${DB_HOST:-host.docker.internal}"
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for database at $DB_HOST:$DB_PORT..."

python - <<'PY'
import os
import socket
import sys
import time

host = os.getenv("DB_HOST", "host.docker.internal")
port = int(os.getenv("DB_PORT", "5432"))

for i in range(90):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"Database is ready!")
            sys.exit(0)
    except OSError:
        print(f"Waiting... ({i+1}/90)")
        time.sleep(1)
print("Database connection timeout!")
sys.exit(1)
PY

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec "$@"
