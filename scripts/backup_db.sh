#!/usr/bin/env bash
# backup_db.sh — Back up data/elo.db with timestamp, retain last 5 copies.
#
# Usage:
#   bash scripts/backup_db.sh
#   bash scripts/backup_db.sh /path/to/elo.db   # custom source path

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DB_PATH="${1:-$PROJECT_ROOT/data/elo.db}"
BACKUP_DIR="$PROJECT_ROOT/data/backups"
KEEP=5

if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Generate timestamped backup filename
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_FILE="$BACKUP_DIR/elo-${TIMESTAMP}.db"

# Use sqlite3 .backup if available (ensures consistent copy even under WAL),
# otherwise fall back to cp.
if command -v sqlite3 &>/dev/null; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
    echo "Backup created (sqlite3 .backup): $BACKUP_FILE"
else
    cp "$DB_PATH" "$BACKUP_FILE"
    echo "Backup created (file copy): $BACKUP_FILE"
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "  Size: $BACKUP_SIZE"

# Prune old backups — keep the newest $KEEP files
BACKUPS=($(ls -1t "$BACKUP_DIR"/elo-*.db 2>/dev/null))
TOTAL=${#BACKUPS[@]}

if [ "$TOTAL" -gt "$KEEP" ]; then
    PRUNE_COUNT=$((TOTAL - KEEP))
    echo "Pruning $PRUNE_COUNT old backup(s) (keeping $KEEP)..."
    for ((i = KEEP; i < TOTAL; i++)); do
        echo "  Removing: $(basename "${BACKUPS[$i]}")"
        rm -f "${BACKUPS[$i]}"
    done
fi

echo "Done. $((TOTAL > KEEP ? KEEP : TOTAL)) backup(s) retained."
