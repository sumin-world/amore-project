#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load env
set -a
[ -f .env ] && source .env
set +a

export DEMO_MODE=true

# DB init safe
PYTHONPATH=. python scripts/init_db.py >/dev/null || true

# 분석만 돌려서 Why report 갱신 (수집은 DEMO_MODE에서 자동 스킵)
PYTHONPATH=. python scripts/analyze.py

# Run UI
streamlit run app.py
