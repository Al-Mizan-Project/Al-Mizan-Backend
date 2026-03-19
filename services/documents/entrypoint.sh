#!/bin/sh

set -e

if [ "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL/PgBouncer..."
    host="${DATABASE_URL#*@}"
    host="${host%%/*}"
    port="${host##*:}"
    host="${host%%:*}"

    while ! nc -z "$host" "$port"; do
      sleep 0.5
    done
    echo "PostgreSQL check completed."
fi

if [ "$MINIO_URL" ]; then
    echo "Waiting for MinIO..."
    host="${MINIO_URL#*//}"
    port="${host##*:}"
    host="${host%%:*}"

    while ! nc -z "$host" "$port"; do
      sleep 0.5
    done
    echo "MinIO check completed."
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"
