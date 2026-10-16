.PHONY: install check lint typecheck test guard run dev-up dev-down web web-check web-preview

BACKEND := cd backend &&

install:
	$(BACKEND) uv sync

lint:
	$(BACKEND) uv run ruff check src tests && uv run ruff format --check src tests

typecheck:
	$(BACKEND) uv run mypy

test:
	$(BACKEND) uv run pytest

guard:
	python3 scripts/check_no_order_apis.py

check: lint typecheck test guard

run:
	$(BACKEND) uv run uvicorn aicfo.main:app --reload --port 8000

dev-up:
	docker compose -f infra/docker-compose.yml up -d

dev-down:
	docker compose -f infra/docker-compose.yml down

web:
	cd frontend && npm install && npm run dev

web-check:
	cd frontend && npm run lint && npm run typecheck && npm run build

web-preview:
	cd frontend && npm run build:preview
