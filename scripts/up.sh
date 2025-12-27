#!/usr/bin/env bash
set -e

# Build + start dashboard container
docker compose -f compose.yml up -d --build dashboard

echo ""
echo "[OK] Dashboard is up."
echo "Open: http://localhost:8501"
