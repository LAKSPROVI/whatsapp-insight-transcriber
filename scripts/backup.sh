#!/bin/sh
# Automated backup script for WIT
set -eu

BACKUP_DIR="/opt/backups/wit"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
TMP_UPLOADS_DIR="/tmp/wit-backup-uploads-${DATE}"

set -a
[ -f ./.env ] && . ./.env
set +a

mkdir -p "$BACKUP_DIR"

# PostgreSQL backup
echo "Backing up PostgreSQL..."
if ! docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$BACKUP_DIR/db_${DATE}.sql.gz"; then
  echo "Database backup failed" >&2
  exit 1
fi

# Uploads backup
echo "Backing up uploads..."
rm -rf "$TMP_UPLOADS_DIR"
if docker compose cp backend:/app/data/uploads "$TMP_UPLOADS_DIR" 2>/dev/null; then
  tar -C "$(dirname "$TMP_UPLOADS_DIR")" -czf "$BACKUP_DIR/uploads_${DATE}.tar.gz" "$(basename "$TMP_UPLOADS_DIR")"
  rm -rf "$TMP_UPLOADS_DIR"
else
  if docker compose ps --status running backend >/dev/null 2>&1; then
    echo "No uploads to backup"
  else
    echo "Backend container unavailable for uploads backup" >&2
    exit 1
  fi
fi

# Cleanup old backups
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.gz" -mtime +"$RETENTION_DAYS" -delete

echo "Backup complete: $BACKUP_DIR"
ls -la "$BACKUP_DIR/"
