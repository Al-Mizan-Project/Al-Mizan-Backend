#!/bin/sh

set -eu

# Wait for PostgreSQL
if [ -n "${DATABASE_URL:-}" ]; then
    echo "Waiting for PostgreSQL..."
    python - <<PY
import os
import socket
import sys
import time

db_host = os.getenv("DB_HOST", "host.docker.internal")
db_port = int(os.getenv("DB_PORT", "5432"))

for _ in range(90):
    try:
        with socket.create_connection((db_host, db_port), timeout=2):
            print("PostgreSQL is ready!")
            sys.exit(0)
    except OSError:
        time.sleep(1)
print("PostgreSQL failed to become ready")
sys.exit(1)
PY
fi

# Wait for MinIO if configured
if [ -n "${MINIO_HOST:-}" ]; then
    echo "Waiting for MinIO..."
    python - <<PY
import os
import socket
import sys
import time

minio_host = os.getenv("MINIO_HOST", "host.docker.internal")
minio_port = int(os.getenv("MINIO_PORT", "9000"))

for _ in range(90):
    try:
        with socket.create_connection((minio_host, minio_port), timeout=2):
            print("MinIO is ready!")
            sys.exit(0)
    except OSError:
        time.sleep(1)
print("MinIO failed to become ready")
sys.exit(1)
PY
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"