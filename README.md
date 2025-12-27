# Amore Project (Docker-first)

## Prereq
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)
- Docker running

Check:
docker --version
docker compose version

## First-time setup
1) Clone
git clone <REPO_URL>
cd amore-project

2) Create env
cp .env.example .env
# edit .env if needed (never commit .env)

3) Start dashboard
./scripts/up.sh

4) Run pipeline once (generates CSV into ./data)
./scripts/run.sh

Open:
http://localhost:8501

## Daily usage
Start dashboard:
./scripts/up.sh

Run pipeline:
./scripts/run.sh

Stop:
./scripts/down.sh

## Troubleshooting
If 8501 is busy:
./scripts/down.sh

Full reset (last resort):
./scripts/down.sh
docker system prune -af
./scripts/up.sh
