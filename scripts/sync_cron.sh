#!/usr/bin/env bash
# ==============================================================================
#  FINART S.A.S. · Sincronización automática de órdenes (Linux Cron)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$DIR"

mkdir -p logs
LOG_FILE="logs/sync.log"

echo "===================================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando sincronización de órdenes..." >> "$LOG_FILE"

# Activar venv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

if python sync.py >> "$LOG_FILE" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sincronización exitosa." >> "$LOG_FILE"
else
    echo "[ERROR] [$(date '+%Y-%m-%d %H:%M:%S')] Error en la sincronización." >> "$LOG_FILE"
    exit 1
fi
echo "" >> "$LOG_FILE"
