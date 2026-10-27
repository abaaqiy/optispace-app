#!/bin/sh
set -eu

cd /app

# Free Render services have no pre-deploy job or shell. Apply pending migrations
# at startup; an error stops the deploy before the web server begins accepting
# requests. The database and all persistent records remain in PostgreSQL.
python backend/manage.py migrate --noinput

# One process keeps memory and database use suitable for the Free 512 MB plan.
# Gunicorn receives termination signals directly because the shell is replaced.
exec gunicorn config.wsgi:application \
    --chdir backend \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 \
    --threads 4 \
    --timeout 90 \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
