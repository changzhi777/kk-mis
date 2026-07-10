#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
if [ -f .env ]; then
  set -a; source .env; set +a
fi
# 端口走环境变量：开发默认 8000，生产 .env 设 APP_PORT=8200 对齐 Nginx
exec python -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}" --log-level info
