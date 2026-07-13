[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [services](../) > **meeting-notes**

# services/meeting-notes · 会议纪要主应用

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/services/` 而非仓库根，改为 `../../../CLAUDE.md`；补齐 mis-system 层级为 4 段面包屑）；修正测试段（原"未配 pytest"已过期，实际 `tests/` 已有 3 文件：test_status_machine / test_safe_filename / test_upload_security，2026-07-12 后补齐）。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-mis` 会议纪要核心服务：上传音频 → ASR 转写 → LLM 智能整理 → 持久化。整合 MLX Whisper 本地 ASR 节点与多供应商 LLM（智谱 GLM-4.7 / minimax / 本地 oMLX），输出结构化纪要（摘要 / 要点 / 决策 / 行动项 / 参会人）。

设计要点：
- **异步流水线**：上传接口立即返回，后台任务跑 ASR + LLM
- **多 LLM 切换**：客户端上传时可选 `glm` / `minimax` / `omlx`
- **JWT 共享**：与 admin 服务共用 `JWT_SECRET`，token 互通
- **路径安全**：`_safe_filename()` 防路径遍历

---

## 入口与启动 (Entry Point)

- **入口文件**: `app/main.py`
- **运行命令**:
  ```bash
  cd services/meeting-notes
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python -m app.main
  ```
- **默认监听**: `0.0.0.0:8200`（`APP_PORT`）
- **健康检查**: `GET /health`（同时检查 ASR 节点 + 报告 LLM providers）
- **LLM 列表**: `GET /llm/providers`
- **OpenAPI 文档**: `GET /docs`

### 启动日志关键项（main.py:23-30）
- 监听 host:port
- 数据库类型（sqlite/postgres）
- LLM 供应商（glm-4.7 / minimax / omlx）
- ASR Cluster URL

---

## 对外接口 (External Interfaces)

所有路由挂在 `/api/v1/meetings` 前缀（routes/meetings.py:40-44）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/meetings/upload` | 上传音频（multipart），后台任务跑 ASR + LLM |
| GET | `/api/v1/meetings` | 列表（分页 + status 过滤） |
| GET | `/api/v1/meetings/{id}` | 详情（含 transcript / summary / key_points / decisions / action_items） |
| DELETE | `/api/v1/meetings/{id}` | 删除（含音频文件） |

### 上传参数（POST /upload）
- `audio: UploadFile` — 必填，最大 500MB（`MAX_UPLOAD_MB`）
- `title: str` — 必填，1-255 字
- `description: str` — 选填，≤2000 字
- `meeting_date: str` — 选填，ISO 8601
- `language: str` — 默认 `zh`
- `llm_provider: str` — `glm` / `minimax` / `omlx`，默认 `glm`

### 响应示例（UploadResponse）
```json
{
  "meeting_id": 123,
  "filename": "周会-2026-07-12.m4a",
  "size_mb": 12.3,
  "status": "uploaded",
  "message": "音频已上传，ASR + GLM LLM 整理任务已启动"
}
```

### 状态机（MeetingStatus）
```
UPLOADED → TRANSCRIBING → TRANSCRIBED → SUMMARIZING → COMPLETED
                                              ↓
                                          FAILED（带 error_message）
```

---

## 关键依赖与配置 (Dependencies & Config)

### requirements.txt
```
# 核心
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
pyjwt>=2.8
pydantic>=2.5.0
pydantic-settings>=2.1.0

# 数据库
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0

# HTTP
httpx>=0.27.0
tenacity>=8.2.0  # LLM 重试

# 工具
python-dotenv>=1.0.0
```

### 关键环境变量（app/config.py）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | 8000（与 dev proxy 一致） | 实际生产 8200 |
| `DB_DRIVER` | `sqlite` | |
| `POSTGRES_DB` | `kk_mis` | ⚠️ 与 admin 不同 |
| `POSTGRES_USER` | `postgres` | ⚠️ 不是 `kk_mis` |
| `REDIS_DB` | 0 | |
| `GLM_API_KEY` | 空 | 智谱 GLM |
| `GLM_MODEL` | `glm-4.7` | |
| `MINIMAX_API_KEY` | 空 | minimax |
| `MINIMAX_MODEL` | `MiniMax-Text-01` | |
| `OMLX_ENABLED` | `true` | 本地 LLM |
| `OMLX_BASE_URL` | `http://localhost:8008/v1` | |
| `OMLX_MODEL` | `gemma-4-e4b-it-4bit` | |
| `ASR_CLUSTER_URL` | `http://localhost:9100` | 集群管理 |
| `DEFAULT_ASR_NODE_URL` | `http://100.88.88.34:9000` | Tailscale Mac |
| `MLX_ASR_API_KEY` | `kk-mis-asr-local-dev-key-2026` | ⚠️ 与 mlx-asr 服务一致 |
| `JWT_SECRET` | `kk-mis-jwt-secret-change-in-prod` | ⚠️ 与 admin 一致 |
| `MAX_UPLOAD_MB` | 500 | |

---

## 数据模型 (Data Models)

### Meeting 模型（app/models.py）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigInteger (SQLite: Integer) | 主键 |
| title | String(255) | 必填，索引 |
| description | Text | |
| meeting_date | DateTime | 索引 |
| status | String(32) | uploaded/transcribing/transcribed/summarizing/completed/failed |
| audio_filename | String(255) | 原文件名 |
| audio_path | String(512) | 服务端路径 |
| audio_size_bytes | BigInteger | |
| audio_duration | Float | ASR 提取 |
| language | String(16) | zh/en |
| raw_transcript | Text | ASR 原始文本 |
| segments | JSON | List[{id, start, end, text, speaker}] |
| asr_model | String(128) | |
| asr_node_id | String(64) | mlx-mac-m5 等 |
| summary | Text | LLM 摘要 |
| key_points | JSON | List[str] |
| decisions | JSON | List[str] |
| action_items | JSON | List[{task, owner, deadline, priority}] |
| llm_model | String(128) | |
| error_message | Text | |
| created_at / updated_at / completed_at | DateTime | |

### Schema（app/schemas.py）
- `MeetingCreate` / `MeetingResponse` / `MeetingListResponse`
- `Segment` / `ActionItem` / `UploadResponse`
- `HealthResponse` / `MeetingStatus`（enum）

---

## 服务层 (Service Layer)

### ASR 客户端（app/services/asr_client.py）
- **直接调用** MLX 节点（不走 asr-cluster 集群，单机开发够用）
- `transcribe(audio_path, language) → dict`
- 自动设置 `X-API-Key` 头
- 默认 node：`http://100.88.88.34:9000`（Tailscale Mac）

> ⚠️ 当前实现直接调单节点；`asr-cluster` 是未来多节点扩展（已实现但未串入）

### LLM 客户端（app/services/llm.py）
- `LLMClient(provider: "glm" | "minimax" | "omlx")`
- `chat(messages, ...)` — 普通聊天
- `chat_json(messages, ...)` — JSON 响应（自动剥 ` ```json ` 包裹）
- `@retry(stop=3, wait_exponential)` — 失败重试
- oMLX 不支持 `response_format`，自动跳过
- `generate_meeting_summary(transcript, provider)` — 会议专用 Prompt

### MeetingService（app/services/notes.py）
编排 ASR + LLM 全流程：
1. 状态置 `TRANSCRIBING` → ASR → 状态置 `TRANSCRIBED`
2. 状态置 `SUMMARIZING` → LLM → 状态置 `COMPLETED`
3. 任何异常 → 状态置 `FAILED` + 写 `error_message`

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-13 续跑更新）
- ✅ pytest 已配置（2026-07-12 后补齐），3 文件全过：
  - `tests/test_status_machine.py` — 会议状态机（uploaded→transcribing→completed/failed）
  - `tests/test_safe_filename.py` — 路径遍历防护（`_safe_filename()`）
  - `tests/test_upload_security.py` — 上传安全校验
- `tests/conftest.py` — 测试 fixtures

### 运行
```bash
cd services/meeting-notes
PYTHONPATH=. pytest tests/ -v
```

### 测试基础设施
- mock ASR + LLM（monkeypatch 替换 `ASRClusterClient.transcribe` 和 `generate_meeting_summary`）
- 状态机测试覆盖异常路径 → `FAILED` + `error_message`
- 上传安全测试覆盖路径遍历、文件名 sanitize

---

## 常见问题 (FAQ)

**Q1: 上传后一直停在上传中？**
A: 后台任务在跑 ASR（分钟级）+ LLM（秒级）。查日志 `[Meeting N processed: status=...]`。

**Q2: ASR 调用失败？**
A: 检查 MLX 节点是否可达（`http://100.88.88.34:9000/health`，Tailscale 是否连通），检查 `MLX_ASR_API_KEY` 是否一致。

**Q3: LLM 调用失败？**
A: `GET /llm/providers` 看 configured 状态；GLM 检查 `GLM_API_KEY`；oMLX 检查 `OMLX_BASE_URL`（默认 `http://localhost:8008/v1`）。

**Q4: 跨服务 token 验证失败？**
A: meeting-notes 与 admin 必须共享 `JWT_SECRET`。见 `app/security.py::verify_jwt`。

**Q5: 上传 413？**
A: 文件超过 `MAX_UPLOAD_MB`（默认 500MB）。生产可调大。

---

## 相关文件清单 (Key Files)

### 应用骨架
- `app/main.py` — FastAPI app + lifespan + CORS
- `app/config.py` — Settings
- `app/db.py` — async engine + SessionLocal
- `app/security.py` — JWT 验证（用 admin 的 secret）
- `app/models.py` — Meeting 模型
- `app/schemas.py` — Pydantic schemas + enums

### 路由
- `app/routes/__init__.py`
- `app/routes/meetings.py` — 上传/列表/详情/删除

### 服务层（app/services/）
- `asr_client.py` — ASRClusterClient（直接调 MLX 节点）
- `llm.py` — LLMClient + generate_meeting_summary
- `notes.py` — MeetingService 编排器

### 测试（tests/）
- `conftest.py` — fixtures
- `test_status_machine.py` — 状态机
- `test_safe_filename.py` — 路径遍历防护
- `test_upload_security.py` — 上传安全

---

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑：修正面包屑路径；测试段从"未配 pytest"更新为"3 文件全过"
- 2026-07-12 15:55:11 — 初始化模块文档
