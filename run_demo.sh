#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

set -a
[ -f .env ] && source .env
set +a
export DEMO_MODE=true

PYTHONPATH=. python scripts/init_db.py  2>/dev/null || true
PYTHONPATH=. python scripts/analyze.py
streamlit run app.py
