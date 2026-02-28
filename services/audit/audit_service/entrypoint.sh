# Exit immediately if a command exits with a non-zero status
set -e

echo "Waiting for postgres..."

# Optional: Wait for the database container to actually be ready
# (Requires netcat/nc to be installed in the docker image)
# while ! nc -z db 5432; do
#   sleep 0.1
# done

echo "PostgreSQL started"

echo "Running migrations..."
# Run migrations for all databases
python manage.py migrate --database=ledger
python manage.py migrate --database=read

echo "Migrations completed"

# Execute the main container command (defined in Dockerfile or Compose)
exec "$@"