#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
if [ -f .env ]; then
  set -a; source .env; set +a
fi
exec python -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8300}" --log-level info
