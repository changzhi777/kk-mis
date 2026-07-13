[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [services](../) > **mlx-asr**

# services/mlx-asr · Mac 本地 ASR 节点

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/services/` 而非仓库根，改为 `../../../CLAUDE.md`；补齐 mis-system 层级为 4 段面包屑）；内容保持（测试状态"未配 pytest"仍准确，是系统内唯一未配测试的服务，建议优先补齐）。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

基于 **MLX Whisper** 的本地语音转文字服务，专为 **Apple Silicon Mac** 优化（MLX 框架用 Metal GPU 加速）。作为 `asr-cluster` 集群的 worker 节点之一，被 `meeting-notes` 主应用通过 HTTP 调用。

设计要点：
- **懒加载 + 预热**：lifespan 启动时后台任务预热模型（避免首次请求阻塞）
- **模型补丁**：`_ensure_mlx_whisper_patched()` 兼容新版 transformers config（50+ 字段 vs mlx_whisper dataclass 10 字段）
- **API Key 鉴权**：所有转写接口需要 `X-API-Key` 头
- **路径安全**：`_safe_filename()` 防止路径遍历

---

## 入口与启动 (Entry Point)

- **入口文件**: `app/main.py`
- **运行命令**:
  ```bash
  cd services/mlx-asr
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python -m app.main
  ```
- **默认监听**: `0.0.0.0:9000`
- **健康检查**: `GET /health`（**无需鉴权**，供集群心跳用）
- **运行要求**: **仅支持 Apple Silicon Mac**（MLX 框架是 Apple 专属）

### 启动流程
1. 打印启动横幅（模型 / 缓存目录 / 监听 / 语言 / max upload）
2. 后台 asyncio 任务跑 `transcriber.warmup()`（首次加载模型到内存）
3. 收到 SIGTERM 时正常关闭

---

## 对外接口 (External Interfaces)

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | ❌ 公开 | 健康检查，返回 model + cache_dir |
| GET | `/models` | ✅ X-API-Key | 当前模型 + loaded 状态 |
| POST | `/transcribe` | ✅ X-API-Key | **核心**：转写音频 |

### POST /transcribe（核心）
**Content-Type**: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audio` | file | ✅ | 音频文件（mp3/wav/m4a/flac），最大 500MB |
| `language` | str | ❌ | 语言代码（zh/en/ja 等），None=自动检测 |
| `beam_size` | int | ❌ | beam search 宽度，默认 5（实际 mlx_whisper 用 greedy） |

**响应**（TranscriptionResult）:
```json
{
  "text": "完整转写文本",
  "language": "zh",
  "duration": 1234.5,
  "model": "mlx-community/whisper-large-v3-turbo",
  "segments": [
    {"id": 0, "start": 0.0, "end": 5.2, "text": "...", "speaker": null},
    ...
  ]
}
```

**错误码**:
- 400 — 文件读取失败
- 401 — 缺/错 X-API-Key
- 413 — 文件超过 500MB
- 500 — 转写失败（模型异常）

### 鉴权
所有非 `/health` 端点强制校验 `X-API-Key`：
```python
if x_api_key != settings.api_key:
    raise HTTPException(401, "Invalid API Key")
```

---

## 关键依赖与配置 (Dependencies & Config)

### requirements.txt
```
mlx-whisper>=0.4.0    # Apple Silicon 专用 MLX 框架
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
pydantic>=2.5.0
httpx>=0.27.0
```

### 关键环境变量（app/config.py）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MLX_ASR_API_KEY` | `kk-mis-asr-default-key-change-me` | ⚠️ 必须与 meeting-notes 一致 |
| `MLX_ASR_MODEL` | `mlx-community/whisper-large-v3-turbo` | HuggingFace 模型 ID |
| `MLX_ASR_CACHE_DIR` | `./models` | 模型本地缓存目录 |
| `MLX_ASR_DEFAULT_LANG` | `zh` | 默认语言 |
| `MLX_ASR_BEAM_SIZE` | 5 | mlx_whisper 暂不支持，仅记录 |
| `MLX_ASR_MAX_DURATION` | 7200 (2h) | 最大音频时长 |
| `MLX_ASR_MAX_UPLOAD_MB` | 500 | |
| `MLX_ASR_LOG_LEVEL` | `INFO` | |

---

## 转写核心 (Transcriber)

### MLXTranscriber（app/transcriber.py）

#### 模型加载
- `warmup()` 在 lifespan 启动时由后台任务触发
- 用 0.5 秒静音（`np.zeros(8000, dtype=np.float32)`）做 lazy load 测试
- 避免首次真实请求时的长时间等待

#### 模型补丁（`_ensure_mlx_whisper_patched`）
新版 transformers 生成的 Whisper `config.json` 含 50+ 字段，但 `mlx_whisper.whisper.ModelDimensions` 是 dataclass 只接受 10 字段。懒加载单次 patch：
- 用 `threading.Lock` 保证线程安全
- 字段映射表：`num_mel_bins → n_mels`，`d_model → n_audio_state + n_text_state` 等
- 未知字段静默忽略
- `global _patched` 标志保证幂等

#### 转写（`transcribe`）
```python
result = mlx_whisper.transcribe(
    str(audio_path),
    path_or_hf_repo=self._model_name,
    language=lang,
    temperature=0,  # greedy decoding (mlx_whisper 不支持 beam)
    verbose=None,
)
```
返回结构构造 `TranscriptionResult`，计算 duration（最后一段的 end）。

---

## 数据模型 (Data Models)

### Pydantic Schema（app/schemas.py）
- `HealthResponse` — `{status, model, cache_dir}`
- `TranscriptionResult` — `{text, language, duration, model, segments: List[Segment]}`
- `Segment` — `{id, start, end, text, speaker}`
- `ErrorResponse` — `{error: str}`

### 异常处理
全局 `@app.exception_handler(HTTPException)` 统一响应格式：
```json
{"error": "<detail>"}
```

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-13 补齐）
- ✅ pytest 已配置，**13 测试全过**（`tests/test_mlx_asr.py`）：
  - `/health` 无鉴权 + `/models` 鉴权
  - `/transcribe` API Key 缺/错 → 401
  - 文件超限 → 413
  - `_safe_filename` 路径遍历防护（5 测试：相对/绝对路径/正常/空/特殊字符）
  - 转写成功（mock `MLXTranscriber.transcribe`，避免真实 mlx_whisper 推理）

### 运行
```bash
cd services/mlx-asr
PYTHONPATH=. pytest tests/ -v
```

### 测试基础设施
- mock `MLXTranscriber.transcribe` + `warmup`（避免 Apple Silicon 专属 mlx_whisper 加载）
- `monkeypatch settings.api_key` + `max_upload_size_mb` 固定值（便于测 413）

### 手动 smoke test
```bash
# 启动后
curl http://localhost:9000/health
# 上传测试
curl -X POST http://localhost:9000/transcribe \
  -H "X-API-Key: kk-mis-asr-local-dev-key-2026" \
  -F "audio=@./test.mp3" \
  -F "language=zh"
```

---

## 常见问题 (FAQ)

**Q1: 启动时模型加载失败？**
A: 检查 `MLX_ASR_CACHE_DIR` 目录权限；检查是否能访问 HuggingFace（模型 `mlx-community/whisper-large-v3-turbo`）；首次会下载 ~1.5GB 模型。

**Q2: 转写返回 401？**
A: 检查 `X-API-Key` 头是否与 meeting-notes 端 `MLX_ASR_API_KEY` 一致。

**Q3: 报 ModelDimensions 字段错误？**
A: 模型版本与 mlx_whisper 不兼容。`_ensure_mlx_whisper_patched` 会自动打补丁；若仍失败，降级模型版本。

**Q4: GPU 没用到？**
A: 确认是 Apple Silicon Mac（M1/M2/M3/M4）；Intel Mac MLX 不可用，需改用纯 CPU 版 whisper。

**Q5: 转写慢？**
A: 模型大小相关。large-v3-turbo 比 large-v3 快约 8x，准确率略低。

---

## 相关文件清单 (Key Files)

### 应用骨架
- `app/main.py` — FastAPI app + lifespan + 鉴权 + 转写端点 + 异常处理
- `app/config.py` — Settings（model_name / cache_dir / api_key）
- `app/schemas.py` — Pydantic models
- `app/transcriber.py` — MLXTranscriber + mlx_whisper monkey-patch

---

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑：修正面包屑路径；标注为系统内唯一未配测试的服务
- 2026-07-12 15:55:11 — 初始化模块文档
