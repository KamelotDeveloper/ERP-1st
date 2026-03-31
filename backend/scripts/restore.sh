#!/bin/bash
# Restore script for GA ERP PostgreSQL database

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 ./backups/ga_erp_backup_20240315_143022.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

DB_NAME="${DB_NAME:-ga_erp}"
DB_USER="${DB_USER:-ga_erp}"
DB_HOST="${DB_HOST:-localhost}"

echo "Starting restore of database: $DB_NAME"
echo "Backup file: $BACKUP_FILE"

if [[ "$BACKUP_FILE" == *.gz ]]; then
    TEMP_FILE=$(mktemp)
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    pg_restore -U "$DB_USER" -h "$DB_HOST" -d "$DB_NAME" -c "$TEMP_FILE"
    rm "$TEMP_FILE"
else
    pg_restore -U "$DB_USER" -h "$DB_HOST" -d "$DB_NAME" -c "$BACKUP_FILE"
fi

echo "Database restored successfully"