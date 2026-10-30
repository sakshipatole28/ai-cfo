#!/bin/sh
# Migrate, optionally load the synthetic demo book, then serve.
set -eu
python -m aicfo.db migrate
if [ "${AICFO_SEED_DEMO:-false}" = "true" ]; then
  python -m aicfo.db seed
fi
exec uvicorn aicfo.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
