# Deploy do Vitalis (EasyPanel). Ver DECISIONS.md D-040 — dev continua SQLite/sem Docker.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq5 postgresql-client ca-certificates curl unzip \
    && curl -fsSL https://downloads.rclone.org/rclone-current-linux-amd64.zip \
        -o /tmp/rclone.zip \
    && unzip -q /tmp/rclone.zip -d /tmp/rclone \
    && install -m 0755 /tmp/rclone/rclone-*/rclone /usr/local/bin/rclone \
    && rm -rf /tmp/rclone /tmp/rclone.zip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gera o estático já no build (WhiteNoise serve em runtime). SECRET_KEY dummy só para o
# comando rodar — não vai para a imagem final como config real.
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=0 python manage.py collectstatic --noinput

RUN chmod +x entrypoint.sh scripts/backup.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
