#!/usr/bin/env bash
set -euo pipefail

# Apply database migrations before starting anything that touches the schema.
# A fresh Postgres volume has no tables, so without this every /api/* call
# 500s until a manual `alembic upgrade head` is run (see issue #146).
#
# `depends_on` without a healthcheck only guarantees the Postgres *container*
# is up, not that it accepts connections, so retry the migration a few times
# to ride out a slow Postgres start.
if [ -n "${DATABASE_URL:-}" ]; then
  attempts=0
  max_attempts="${MAX_MIGRATION_ATTEMPTS:-15}"
  until alembic upgrade head; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge "$max_attempts" ]; then
      echo "alembic upgrade head failed after $max_attempts attempts; aborting." >&2
      exit 1
    fi
    echo "Waiting for database before retrying migrations (attempt $attempts/$max_attempts)..." >&2
    sleep "${MIGRATION_RETRY_SLEEP:-2}"
  done
else
  echo "DATABASE_URL is not set; skipping alembic migrations." >&2
fi

# Start worker in background (queue processing)
python -m app.worker &

# Start API (serves frontend if built)
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
