#!/bin/sh
set -e

# Kubernetes runs migrations once in a dedicated Job and sets RUN_MIGRATIONS=false
# so replicas don't race on the schema.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "==> Alembic migrate"
  cd /app/backend
  alembic upgrade head
fi

WORKERS="${UVICORN_WORKERS:-4}"
echo "==> Starting uvicorn with ${WORKERS} workers (Linux container)"
cd /app
exec uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WORKERS}" \
  --loop asyncio
