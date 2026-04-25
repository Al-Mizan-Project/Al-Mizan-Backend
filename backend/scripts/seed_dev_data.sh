#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BACKEND_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$BACKEND_DIR"

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Running unified dev seed command..."
python manage.py seed_dev_data "$@"

echo "Seed script completed."
