#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Use python3 explicitly (macOS ships python3, not python)
PYTHON="${PYTHON:-python3}"

set -a
[ -f .env ] && source .env
set +a
export DEMO_MODE=true

PYTHONPATH=. "$PYTHON" scripts/init_db.py  2>/dev/null || true
PYTHONPATH=. "$PYTHON" scripts/analyze.py
PYTHONPATH=. "$PYTHON" -m streamlit run app.py --server.port 8502
