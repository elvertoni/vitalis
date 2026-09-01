#!/bin/sh
# Boot do container: aplica migrations (idempotente, 1 réplica) e sobe o gunicorn.
# billing/migrations/0002_seed_plans.py semeia os planos Free/Premium sozinho.
# SERVICE_MODE=cron roda send_due_reminders a cada 15 min em vez do gunicorn.
set -e

python manage.py migrate --noinput

if [ "$SERVICE_MODE" = "cron" ]; then
    echo "[cron] Modo agendador — send_due_reminders a cada 15 min"
    while true; do
        python manage.py send_due_reminders || echo "[cron] ERRO ao rodar send_due_reminders"
        sleep 900
    done
else
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --timeout 60 \
        --access-logfile - \
        --error-logfile -
fi
