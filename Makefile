.PHONY: install check lint typecheck test guard run dev-up dev-down web web-check web-preview \
	db-migrate db-seed db-status automation-up n8n-import llm-status llm-bench init-env e2e

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
	python3 scripts/check_n8n_workflows.py

check: lint typecheck test guard

run:
	$(BACKEND) uv run uvicorn aicfo.main:app --reload --port 8000

dev-up:
	docker compose -f infra/docker-compose.yml up -d

dev-down:
	docker compose -f infra/docker-compose.yml --profile automation down

web:
	cd frontend && npm install && npm run dev

web-check:
	cd frontend && npm run lint && npm run typecheck && npm run build

web-preview:
	cd frontend && npm run build:preview

db-migrate:
	$(BACKEND) uv run python -m aicfo.db migrate

db-seed:
	$(BACKEND) uv run python -m aicfo.db seed

db-status:
	$(BACKEND) uv run python -m aicfo.db status

# Postgres + API container (seeded with the synthetic book) + n8n on http://localhost:5678
automation-up:
	docker compose -f infra/docker-compose.yml --profile automation up -d --build

# Load both workflows, publish the event listener, restart n8n so the webhook registers.
# To switch on the Monday schedule too:  n8n publish:workflow --id=aicfoWeeklySweep  (then restart)
n8n-import:
	docker compose -f infra/docker-compose.yml --profile automation exec n8n n8n import:workflow --separate --input=/workflows
	docker compose -f infra/docker-compose.yml --profile automation exec n8n n8n publish:workflow --id=aicfoReviewEvent
	docker compose -f infra/docker-compose.yml --profile automation restart n8n

llm-status:
	$(BACKEND) uv run python -m aicfo.llm status

# Calls the real Groq/Gemini APIs with synthetic data; needs keys in backend/.env
llm-bench:
	$(BACKEND) uv run python -m aicfo.llm bench --json ../docs/llm-benchmark.json

# Fill in missing secrets in backend/.env (key-encryption key, session secret, automation token).
# Never overwrites a value you already set, and never prints one.
init-env:
	python3 scripts/init_env.py

# Real-browser test of sign-up, invites and roles. Needs the API and console running (README: "Run it").
e2e:
	cd frontend && npm run e2e:live
