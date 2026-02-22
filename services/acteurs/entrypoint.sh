#!/bin/sh
set -eu

DB_HOST="${DB_HOST:-acteurs-db}"
DB_PORT="${DB_PORT:-5432}"

python - <<PY
import os
import socket
import sys
import time

host = os.getenv("DB_HOST", "acteurs-db")
port = int(os.getenv("DB_PORT", "5432"))

for _ in range(90):
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(1)
PY

python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --timeout "${GUNICORN_TIMEOUT:-60}" --access-logfile - --error-logfile -
