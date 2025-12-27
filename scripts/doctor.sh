#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="compose.yml"
PORT="8501"

say() { printf "%s\n" "$*"; }
ok()  { say "[OK] $*"; }
warn(){ say "[WARN] $*"; }
bad() { say "[FAIL] $*"; }

need_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "found: $1"
  else
    bad "missing: $1"
    return 1
  fi
}

check_port_in_use() {
  local p="$1"
  # Try lsof (mac/linux)
  if command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    else
      return 1
    fi
  fi

  # Try ss (linux)
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn | awk '{print $4}' | grep -E "(:|\\.)${p}\$" >/dev/null 2>&1; then
      return 0
    else
      return 1
    fi
  fi

  # Try netstat (fallback)
  if command -v netstat >/dev/null 2>&1; then
    if netstat -an 2>/dev/null | grep -E "LISTEN" | grep -E "[:.]${p}[[:space:]]" >/dev/null 2>&1; then
      return 0
    else
      return 1
    fi
  fi

  warn "cannot check port usage (no lsof/ss/netstat). skipping port check."
  return 2
}

say "== Amore Project Doctor =="
say ""

# 1) Basic files
if [[ -f "$COMPOSE_FILE" ]]; then ok "found: $COMPOSE_FILE"; else bad "missing: $COMPOSE_FILE"; exit 1; fi
if [[ -f "docker/Dockerfile" ]]; then ok "found: docker/Dockerfile"; else bad "missing: docker/Dockerfile"; exit 1; fi
if [[ -f "requirements.txt" ]]; then ok "found: requirements.txt"; else bad "missing: requirements.txt"; exit 1; fi

# 2) Docker presence
need_cmd docker

# 3) Docker daemon running?
if docker info >/dev/null 2>&1; then
  ok "docker daemon is reachable"
else
  bad "docker daemon is NOT reachable"
  say "Fix:"
  say "  - Mac/Windows: Docker Desktop 실행"
  say "  - Linux: sudo systemctl start docker"
  exit 1
fi

# 4) Compose availability
# docker compose is preferred
if docker compose version >/dev/null 2>&1; then
  ok "docker compose is available"
else
  bad "docker compose is not available"
  say "Fix:"
  say "  - Docker Desktop 최신 버전 설치"
  say "  - Linux: docker-compose-plugin 설치"
  exit 1
fi

# 5) Permission sanity (Linux only: docker group)
OS="$(uname -s || true)"
if [[ "$OS" == "Linux" ]]; then
  # Try a harmless command without sudo
  if docker ps >/dev/null 2>&1; then
    ok "docker permission looks OK (no sudo needed)"
  else
    warn "docker ps failed without sudo (permission issue possible)"
    say "Fix (Linux):"
    say "  sudo usermod -aG docker \$USER"
    say "  newgrp docker"
  fi
fi

# 6) Port check
res=0
set +e
check_port_in_use "$PORT"
res=$?
set -e

if [[ $res -eq 0 ]]; then
  warn "port $PORT seems already in use"
  say "Fix:"
  say "  - run: ./scripts/down.sh"
  say "  - or change port mapping in compose.yml"
elif [[ $res -eq 1 ]]; then
  ok "port $PORT is free"
else
  # 2: skipped
  :
fi

# 7) Quick project run suggestion
say ""
say "Next steps:"
say "  make up"
say "  make run"
say "  open http://localhost:${PORT}"
say ""
ok "doctor checks completed"
