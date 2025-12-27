SHELL := /usr/bin/env bash

COMPOSE := docker compose -f compose.yml

.PHONY: help doctor up run down ps logs rebuild clean reset

help:
	@echo "Targets:"
	@echo "  make doctor   - 환경 자동 점검"
	@echo "  make up       - 대시보드 실행(백그라운드)"
	@echo "  make run      - 파이프라인 1회 실행(CSV 생성)"
	@echo "  make down     - 서비스 중지"
	@echo "  make ps       - 컨테이너 상태"
	@echo "  make logs     - 대시보드 로그"
	@echo "  make rebuild  - 강제 리빌드 + up"
	@echo "  make clean    - 생성 데이터 삭제(로컬 ./data/*.csv 등)"
	@echo "  make reset    - down + docker system prune (최후수단)"

doctor:
	@./scripts/doctor.sh

up:
	@./scripts/up.sh

run:
	@./scripts/run.sh

down:
	@./scripts/down.sh

ps:
	@$(COMPOSE) ps

logs:
	@$(COMPOSE) logs -f dashboard

rebuild:
	@$(COMPOSE) down
	@$(COMPOSE) up -d --build dashboard

clean:
	@rm -f data/*.csv || true
	@rm -rf src/__pycache__ || true
	@echo "[OK] cleaned local artifacts"

reset:
	@$(COMPOSE) down || true
	@docker system prune -af
	@echo "[OK] docker reset done. run: make up"
