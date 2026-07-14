#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export DEFAULT_ASR_NODE_URL=http://100.88.88.34:9000
export MLX_ASR_API_KEY=kk-cms-asr-local-dev-key-2026
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 9100 --log-level info
