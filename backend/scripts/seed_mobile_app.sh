#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BACKEND_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$BACKEND_DIR"

if [ "$#" -eq 0 ]; then
  set -- \
    --flush \
    --soumissions-count "${MOBILE_SOUMISSIONS_COUNT:-8}" \
    --notifications-count "${MOBILE_NOTIFICATIONS_COUNT:-12}" \
    --watched-count "${MOBILE_WATCHED_COUNT:-5}"
fi

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Seeding mobile app data..."
python manage.py seed_dev_data "$@"

echo "Mobile seed script completed."
