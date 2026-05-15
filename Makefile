.PHONY: help up up-prod down logs restart migrate revision superuser shell-backend shell-frontend sandbox-build clean

help:
	@echo "khasa — make targets"
	@echo ""
	@echo "  up               поднять dev (с MailHog)"
	@echo "  up-prod          поднять prod (без MailHog, фронт собирается)"
	@echo "  down             остановить всё"
	@echo "  logs             tail -f всех сервисов"
	@echo "  restart          перезапустить backend + frontend"
	@echo "  migrate          alembic upgrade head"
	@echo "  revision m=..    создать миграцию: make revision m='add_chats'"
	@echo "  superuser e=... p=...   создать суперюзера"
	@echo "  sandbox-build    собрать образ khasa-sandbox:latest для агентного режима"
	@echo "  shell-backend    bash в backend-контейнере"
	@echo "  shell-frontend   sh в frontend-контейнере"
	@echo "  clean            down + удалить volume postgres_data"

up:
	docker compose --profile dev up -d --build

up-prod:
	BACKEND_TARGET=prod FRONTEND_TARGET=prod docker compose --profile prod up -d --build

down:
	docker compose --profile dev --profile prod down

logs:
	docker compose logs -f --tail=200

restart:
	docker compose restart backend frontend

migrate:
	docker compose exec backend alembic upgrade head

revision:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

superuser:
	docker compose exec backend python -m app.scripts.create_superuser "$(e)" "$(p)"

sandbox-build:
	docker build -t khasa-sandbox:latest backend/sandbox/

shell-backend:
	docker compose exec backend bash

shell-frontend:
	docker compose exec frontend sh

clean:
	docker compose --profile dev --profile prod down -v
