#!/usr/bin/env sh
set -eu

if [ "${QUEUE_ENABLED:-0}" != "1" ]; then
  echo "QUEUE_ENABLED is not set to 1; worker will not start. Set QUEUE_ENABLED=1 in .env (docker-compose.worker.yml requires it)." >&2
  exit 1
fi

exec python -m app.worker
