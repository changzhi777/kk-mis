#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
if [ -f .env ]; then
  set -a; source .env; set +a
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
