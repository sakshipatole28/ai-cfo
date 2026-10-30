# API image. Build from the repository root: docker build -f backend/Dockerfile .
# Synthetic data only: data/ ships the demo book and the knowledge base, never client data.
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/src ./src
COPY backend/README.md backend/docker-entrypoint.sh ./
COPY data/kb /app/data/kb
COPY data/synthetic /app/data/synthetic
COPY data/ml /app/data/ml
COPY data/evals /app/data/evals
RUN uv sync --locked --no-dev && chmod +x docker-entrypoint.sh

RUN useradd --system --uid 10001 aicfo
USER aicfo
ENV PATH="/app/backend/.venv/bin:$PATH" AICFO_ENV=staging PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
ENTRYPOINT ["./docker-entrypoint.sh"]
