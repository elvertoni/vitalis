#!/bin/sh
# Backup do Vitalis: banco + anexos de exame.
#
# Roda no serviço `vitalis-backup` do EasyPanel (SERVICE_MODE=backup), que usa a mesma
# imagem do app. Guarda os arquivos em /backups, que precisa ser um volume — se for o
# sistema de arquivos do contêiner, o backup morre junto com o contêiner que ele deveria
# proteger.
#
# Envio para fora da máquina (Google Drive, S3) é o passo que fecha a conta: cópia guardada
# no mesmo servidor protege contra engano humano e corrupção de tabela, não contra perder o
# host. Se RCLONE_REMOTE estiver definido e o rclone existir, o script sincroniza; senão
# avisa e segue, para que a falta da credencial nunca impeça o backup local de acontecer.
set -eu

DEST="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
MEDIA_DIR="${MEDIA_ROOT:-/app/media}"

mkdir -p "$DEST"

echo "[$(date -u +%FT%TZ)] backup iniciado"

# ── Banco ────────────────────────────────────────────────────────────────────
# DATABASE_URL vem do ambiente do EasyPanel; pg_dump entende a URL direto.
if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERRO: DATABASE_URL não definida — sem isso não há o que salvar." >&2
    exit 1
fi

DB_FILE="$DEST/vitalis-db-$STAMP.sql.gz"
pg_dump --dbname="$DATABASE_URL" --format=plain --no-owner --no-privileges \
    | gzip -9 > "$DB_FILE"

# Um dump que não abre não é backup. Testa a integridade do gzip antes de confiar nele.
if ! gzip -t "$DB_FILE"; then
    echo "ERRO: dump corrompido, removendo $DB_FILE" >&2
    rm -f "$DB_FILE"
    exit 1
fi
echo "banco:  $(basename "$DB_FILE") ($(wc -c < "$DB_FILE") bytes)"

# ── Anexos (laudos de exame) ─────────────────────────────────────────────────
# Dado sensível de saúde: se sumir, não se reconstrói a partir de lugar nenhum.
if [ -d "$MEDIA_DIR" ]; then
    MEDIA_FILE="$DEST/vitalis-media-$STAMP.tar.gz"
    tar -czf "$MEDIA_FILE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
    gzip -t "$MEDIA_FILE" || { echo "ERRO: tar corrompido" >&2; rm -f "$MEDIA_FILE"; exit 1; }
    echo "anexos: $(basename "$MEDIA_FILE") ($(wc -c < "$MEDIA_FILE") bytes)"
else
    echo "aviso: $MEDIA_DIR não existe — nenhum anexo para salvar."
fi

# ── Cópia externa ────────────────────────────────────────────────────────────
if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null 2>&1; then
    echo "enviando para $RCLONE_REMOTE"
    rclone copy "$DEST" "$RCLONE_REMOTE" --include "vitalis-*-$STAMP.*"
    echo "cópia externa concluída"
else
    echo "aviso: sem cópia externa (RCLONE_REMOTE não definida ou rclone ausente)."
    echo "       o backup existe apenas neste servidor — não protege contra perda do host."
fi

# ── Retenção ─────────────────────────────────────────────────────────────────
find "$DEST" -name 'vitalis-*' -type f -mtime "+$KEEP_DAYS" -print -delete

echo "[$(date -u +%FT%TZ)] backup concluído · $(ls -1 "$DEST"/vitalis-* 2>/dev/null | wc -l) arquivos guardados"
