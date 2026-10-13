#!/usr/bin/env bash
set -e

echo "======================================================="
echo "  FINART S.A.S. · Dashboard ARDP Falabella"
echo "======================================================="

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
