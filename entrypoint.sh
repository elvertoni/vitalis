#!/bin/sh
# Boot do container: aplica migrations (idempotente, 1 réplica) e sobe o gunicorn.
# billing/migrations/0002_seed_plans.py semeia os planos Free/Premium sozinho.
set -e

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
