#!/bin/sh
# Boot do container: aplica migrations (idempotente, 1 réplica) e sobe o gunicorn.
# billing/migrations/0002_seed_plans.py semeia os planos Free/Premium sozinho.
# SERVICE_MODE=cron roda send_due_reminders a cada 15 min em vez do gunicorn.
# SERVICE_MODE=backup roda scripts/backup.sh uma vez por dia.
set -e

if [ "$SERVICE_MODE" = "backup" ]; then
    # Um backup ao subir, para que a primeira cópia não espere um dia, e depois um por dia.
    # Sem migrate: este serviço só lê o banco.
    echo "[backup] Modo backup — dump diário do banco e dos anexos"
    while true; do
        ./scripts/backup.sh || echo "[backup] ERRO ao rodar backup.sh"
        sleep 86400
    done
elif [ "$SERVICE_MODE" = "cron" ]; then
    # Sem migrate aqui: quem aplica é o serviço web, sozinho. Dois containers subindo
    # migrations ao mesmo tempo num deploy é corrida à toa — o agendador só lê e escreve
    # lembretes, e o Django falha alto se o schema estiver atrasado.
    echo "[cron] Modo agendador — send_due_reminders a cada 15 min"
    while true; do
        python manage.py send_due_reminders || echo "[cron] ERRO ao rodar send_due_reminders"
        sleep 900
    done
else
    python manage.py migrate --noinput

    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --timeout 60 \
        --access-logfile - \
        --error-logfile -
fi
