#!/usr/bin/env bash
set -e

docker compose -f compose.yml down
echo "[OK] All services stopped."
