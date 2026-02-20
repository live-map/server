#!/bin/bash
# Daily PostgreSQL backup script for Grapoll
# Usage: Add to crontab: 0 3 * * * /home/ubuntu/grapoll/backend/scripts/backup-db.sh
set -euo pipefail

BACKUP_DIR="/home/ubuntu/grapoll/backend/backups"
CONTAINER="livemap-db"
DB_USER="livemap"
DB_NAME="livemap"
RETAIN_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/grapoll_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup complete: $BACKUP_FILE ($SIZE)"
else
    echo "[$(date)] ERROR: Backup failed or empty" >&2
    exit 1
fi

# Remove backups older than RETAIN_DAYS
find "$BACKUP_DIR" -name "grapoll_*.sql.gz" -mtime +${RETAIN_DAYS} -delete
echo "[$(date)] Cleaned backups older than ${RETAIN_DAYS} days"
