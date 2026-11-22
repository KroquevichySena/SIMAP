#!/bin/sh
set -eu

if [ "${1:-}" != "web" ]; then
    exec "$@"
fi

: "${SECRET_KEY:?Configure SECRET_KEY no ambiente}"
: "${DATABASE_URL:?Configure DATABASE_URL no ambiente}"

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi
python manage.py collectstatic --noinput

exec gunicorn SIMAP.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --error-logfile -
