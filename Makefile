SHELL := /bin/bash

LOCAL_UID := $(shell id -u)
LOCAL_GID := $(shell id -g)

DC := LOCAL_UID=$(LOCAL_UID) LOCAL_GID=$(LOCAL_GID) docker compose -f compose.yml

.PHONY: help doctor up run down ps logs clean reset fix-perms

help:
	@echo "Targets:"
	@echo "  make doctor   - 환경 점검(도커/포트/파일)"
	@echo "  make up       - 대시보드 실행"
	@echo "  make run      - 파이프라인 1회 실행(CSV 생성)"
	@echo "  make logs     - 대시보드 로그 보기"
	@echo "  make ps       - 컨테이너 상태"
	@echo "  make down     - 컨테이너 종료"
	@echo "  make clean    - 로컬 산출물 정리(data/reports/logs/snapshots)"
	@echo "  make reset    - down + clean + 이미지 포함 강제 초기화(주의)"
	@echo "  make fix-perms- (리눅스) root로 찍힌 파일 권한 복구"

doctor:
	@./scripts/doctor.sh

up:
	@$(DC) up -d --build dashboard
	@echo ""
	@echo "[OK] Dashboard is up."
	@echo "Open: http://localhost:8501"
	@$(DC) ps

run:
	@$(DC) run --rm app
	@echo ""
	@echo "[OK] latest files in ./data:"
	@ls -al data || true

logs:
	@$(DC) logs -f dashboard

ps:
	@$(DC) ps

down:
	@$(DC) down
	@echo "[OK] All services stopped."

clean:
	@rm -rf data/*.csv 2>/dev/null || true
	@rm -rf reports/* 2>/dev/null || true
	@rm -rf logs/* 2>/dev/null || true
	@rm -rf snapshots/* 2>/dev/null || true
	@find src -name "__pycache__" -type d -prune -exec rm -rf {} \; 2>/dev/null || true
	@echo "[OK] cleaned local artifacts"

reset: down clean
	@docker system prune -af
	@echo "[OK] docker system pruned"

fix-perms:
	@echo "[INFO] Fixing file ownership under data/logs/reports/snapshots/src (may require sudo)."
	@sudo chown -R $(shell id -un):$(shell id -gn) data logs reports snapshots src || true
	@echo "[OK] Done."
