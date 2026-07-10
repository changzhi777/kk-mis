#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
# 加载 .env
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
export HF_ENDPOINT=https://hf-mirror.com
export MLX_ASR_MODEL=./models/belle-whisper-zh-punct
export MLX_ASR_API_KEY=kk-mis-asr-local-dev-key-2026
echo "API_KEY: ${MLX_ASR_API_KEY:0:10}..."
echo "MODEL: $MLX_ASR_MODEL"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 9000 --log-level info
