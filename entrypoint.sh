#!/bin/sh
set -e

# If arguments are passed to the script (like "bash" or "python"), run those instead
if [ $# -gt 0 ]; then
    exec "$@"
fi

# ----------------------------------------------------------------
# OPTIONAL: Make Migrations
# This generates new migration files based on model changes.
# NOTE: The container user must have WRITE access to the app folders.
# ----------------------------------------------------------------
echo "Checking for model changes..."
python manage.py makemigrations --noinput || echo "Make migrations failed (possibly permission error), skipping..."

# ----------------------------------------------------------------
# Wait for Database and Migrate
# We loop here because the DB might not be ready immediately.
# ----------------------------------------------------------------
echo "Waiting for database..."
until python manage.py migrate_schemas --shared --noinput; do
  echo "Database not ready yet. Retrying in 3 seconds..."
  sleep 3
done

echo "Running tenant migrations..."
python manage.py migrate_schemas --noinput

# ----------------------------------------------------------------
# Collect Static Files
# ----------------------------------------------------------------
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Collectstatic failed, continuing..."

# ----------------------------------------------------------------
# Start Server
# ----------------------------------------------------------------
echo "Starting gunicorn..."
exec gunicorn invoice.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --log-level warning