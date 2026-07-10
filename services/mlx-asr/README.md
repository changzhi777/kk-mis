# MLX Whisper ASR 服务

> 本地 Mac（Apple Silicon）上的语音转文字服务，零云成本、隐私强。

## 🚀 快速启动

```bash
# 1. 安装依赖
cd services/mlx-asr
pip install -r requirements.txt

# 2. 启动服务（首次会自动下载模型 ~800MB）
python -m app.main
# 或
uvicorn app.main:app --host 0.0.0.0 --port 9000
```

服务运行在 `http://localhost:9000`

## 📡 API

### 健康检查（无需鉴权）
```bash
curl http://localhost:9000/health
```

### 转写
```bash
curl -X POST http://localhost:9000/transcribe \
  -H "X-API-Key: kk-mis-asr-local-dev-key-2026" \
  -F "audio=@meeting.mp3" \
  -F "language=zh"
```

### 响应示例
```json
{
  "text": "今天我们讨论 V2.0 的需求优先级...",
  "language": "zh",
  "duration": 60.5,
  "model": "mlx-community/whisper-large-v3-turbo",
  "segments": [
    {"id": 0, "start": 0.0, "end": 5.2, "text": "...", "speaker": null}
  ]
}
```

## 🛠 模型

| 模型 | 大小 | 中文 CER | 速度（M2/M5）|
|---|---|---|---|
| mlx-community/whisper-tiny | 39M | ~30% | ~30x 实时 |
| mlx-community/whisper-base | 74M | ~22% | ~20x |
| mlx-community/whisper-small | 244M | ~15% | ~10x |
| mlx-community/whisper-medium | 769M | ~12% | ~5x |
| **mlx-community/whisper-large-v3** | 1.5G | ~10% | ~2x |
| **mlx-community/whisper-large-v3-turbo** ⭐ | 809M | ~10% | ~5x |

## 🌐 网络访问

通过 **Tailscale** 暴露给云服务器（推荐）：
1. Mac: `tailscale up`
2. 服务器: 调用 `http://<mac-tailscale-ip>:9000/transcribe`

## 📂 目录结构

```
mlx-asr/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── transcriber.py   # 转写核心
│   ├── schemas.py       # Pydantic 模型
│   └── config.py        # 配置
├── models/              # 模型缓存
├── logs/                # 日志
├── tests/               # 测试
├── .env                 # 环境变量
└── requirements.txt
```

## 🧪 测试

```bash
# 启动服务后另开终端
python -c "
import httpx
with open('test.mp3', 'rb') as f:
    r = httpx.post(
        'http://localhost:9000/transcribe',
        headers={'X-API-Key': 'kk-mis-asr-local-dev-key-2026'},
        files={'audio': f},
        data={'language': 'zh'}
    )
print(r.json())
"
```

## 📜 License

MIT