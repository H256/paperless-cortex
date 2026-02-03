#!/usr/bin/env bash
set -euo pipefail

# Start worker in background (queue processing)
python -m app.worker &

# Start API (serves frontend if built)
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
