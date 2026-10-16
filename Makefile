.PHONY: install check lint typecheck test guard run dev-up dev-down

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
