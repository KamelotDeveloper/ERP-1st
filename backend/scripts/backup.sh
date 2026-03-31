#!/bin/bash
# Backup script for GA ERP PostgreSQL database

set -e

DB_NAME="${DB_NAME:-ga_erp}"
DB_USER="${DB_USER:-ga_erp}"
DB_HOST="${DB_HOST:-localhost}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/ga_erp_backup_${TIMESTAMP}.sql"

echo "Starting backup of database: $DB_NAME"

pg_dump -U "$DB_USER" -h "$DB_HOST" -F c -b -v -f "$BACKUP_FILE" "$DB_NAME"

echo "Backup created: $BACKUP_FILE"

gzip "$BACKUP_FILE"
echo "Backup compressed: ${BACKUP_FILE}.gz"

find "$BACKUP_DIR" -name "ga_erp_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "Old backups (>$RETENTION_DAYS days) cleaned up"

echo "Backup completed successfully"