#!/usr/bin/env sh
set -eu

if [ "${QUEUE_ENABLED:-0}" != "1" ]; then
  echo "QUEUE_ENABLED is not set to 1; worker will not start."
  exit 0
fi

exec python -m app.worker
