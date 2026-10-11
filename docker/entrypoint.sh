#!/bin/sh
# Entrypoint for the slim image: wait for the database, migrate, make sure the admin exists, serve.
set -eu
cd /app
python manage.py wait_for_db
python manage.py migrate --noinput
python manage.py ensure_admin
if [ "${MVAULT_PROVISION_BUCKETS:-false}" = "true" ]; then
    python manage.py provision_storage || echo "WARNING: could not provision buckets; create them manually." >&2
fi
exec gunicorn mvault_project.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" --workers "${GUNICORN_WORKERS:-3}" --timeout "${GUNICORN_TIMEOUT:-120}" --access-logfile -
