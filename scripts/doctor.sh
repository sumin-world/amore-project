#!/usr/bin/env bash
set -euo pipefail

echo "== Amore Project Doctor =="

need_files=("compose.yml" "docker/Dockerfile" "requirements.txt")
for f in "${need_files[@]}"; do
  if [[ -f "$f" ]]; then
    echo "[OK] found: $f"
  else
    echo "[FAIL] missing: $f"
    exit 1
  fi
done

need_dirs=("docker" "src" "data" "logs" "reports" "snapshots" "scripts")
for d in "${need_dirs[@]}"; do
  if [[ -d "$d" ]]; then
    echo "[OK] found dir: $d"
  else
    echo "[INFO] creating dir: $d"
    mkdir -p "$d"
  fi
done

if docker info >/dev/null 2>&1; then
  echo "[OK] docker daemon is reachable"
else
  echo "[FAIL] docker daemon not reachable. Start Docker Desktop (Mac/Win) or docker service (Linux)."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  echo "[OK] docker compose is available"
else
  echo "[FAIL] docker compose not available"
  exit 1
fi

if docker ps >/dev/null 2>&1; then
  echo "[OK] docker permission looks OK (no sudo needed)"
else
  echo "[WARN] docker permission may require sudo (Linux)."
  echo "      Fix: sudo usermod -aG docker \$USER && newgrp docker"
fi

if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:8501 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[FAIL] port 8501 is already in use."
    echo "       Fix: make down"
    exit 1
  else
    echo "[OK] port 8501 is free"
  fi
else
  echo "[INFO] lsof not found. Skipping port check."
fi

if [[ -f ".env" ]]; then
  echo "[OK] found: .env"
else
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "[INFO] created .env from .env.example (edit if needed)"
  else
    echo "[WARN] .env.example not found. Create .env manually if needed."
  fi
fi

echo ""
echo "Next steps:"
echo "  make up"
echo "  make run"
echo "  open http://localhost:8501"
echo ""
echo "[OK] doctor checks completed"
