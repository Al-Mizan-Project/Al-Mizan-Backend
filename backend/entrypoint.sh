#!/bin/sh
set -eu

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
python - <<'PY'
import os
import socket
import sys
import time


def wait_for(host, port, label):
    for attempt in range(90):
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{label} is ready")
                return True
        except OSError:
            print(f"Waiting for {label}... ({attempt + 1}/90)")
            time.sleep(1)
    return False


db_ready = wait_for(os.getenv("DB_HOST", "postgres"), int(os.getenv("DB_PORT", "5432")), "PostgreSQL")
redis_ready = wait_for(os.getenv("REDIS_HOST", "redis"), int(os.getenv("REDIS_PORT", "6379")), "Redis")
sys.exit(0 if db_ready and redis_ready else 1)
PY

echo "Running default migrations..."
python manage.py migrate --noinput

same_database_mode=false
if [ "${DB_NAME:-}" = "${DB_LEDGER_NAME:-${DB_NAME:-}}" ] \
  && [ "${DB_NAME:-}" = "${DB_READ_NAME:-${DB_NAME:-}}" ] \
  && [ "${DB_HOST:-}" = "${DB_LEDGER_HOST:-${DB_HOST:-}}" ] \
  && [ "${DB_HOST:-}" = "${DB_READ_HOST:-${DB_HOST:-}}" ] \
  && [ "${DB_PORT:-}" = "${DB_LEDGER_PORT:-${DB_PORT:-}}" ] \
  && [ "${DB_PORT:-}" = "${DB_READ_PORT:-${DB_PORT:-}}" ]; then
  same_database_mode=true
fi

if [ "$same_database_mode" = "true" ]; then
  echo "Single database mode detected; skipping separate ledger/read migration passes"
else
  echo "Running audit migrations..."
  python manage.py migrate ledger --database=ledger --noinput || true
  python manage.py migrate integrity --database=ledger --noinput || true
  python manage.py migrate readstore --database=read --noinput || true
fi

echo "Ensuring routed runtime tables exist..."
python manage.py ensure_runtime_tables || true

echo "Bootstrapping admin if available..."
python manage.py bootstrap_admin || true

exec "$@"
