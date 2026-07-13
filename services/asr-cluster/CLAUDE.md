[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [services](../) > **asr-cluster**

# services/asr-cluster · ASR 集群管理

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：
  - 修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/services/` 而非仓库根，改为 `../../../CLAUDE.md`；补齐 mis-system 层级为 4 段面包屑）；
  - **修正"依赖缺失"过期描述**：原"项目根没有 requirements.txt"已过期，`requirements.txt` 已存在（4 依赖：fastapi / uvicorn[standard] / pydantic / httpx）；
  - **修正测试段**：原"未配 pytest"已过期，`tests/` 已有 2 文件（test_security + integration/test_cluster）；
  - **补容器化说明**：Dockerfile + docker-compose.yml + .env.example + .dockerignore 已就绪；
  - **修正 FAQ Q5**：原"没有 requirements.txt"已过期。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-mis` ASR 集群管理器：注册多个 MLX Whisper 节点，心跳监控健康状态，提供负载均衡的任务分发。当前用于未来多 Mac 节点扩展（生产环境已有 meeting-notes 直接调单节点的简化路径）。

设计要点：
- **节点注册表**（`NodeRegistry`）：节点 ID → `ASRNode`
- **心跳监控**（`HeartbeatMonitor`）：每 10 秒检查所有节点 `/health`，超时 30s 标 `OFFLINE`
- **负载均衡**（`LoadBalancer`）：`priority ASC, current_tasks ASC` 排序取最优
- **状态机**: `OFFLINE → HEALTHY → BUSY → DEGRADED`
- **单进程内存态**：不持久化，重启后丢失（适合 dev/小规模）

> ⚠️ 当前生产环境 `meeting-notes/app/services/asr_client.py` **未串入**本集群，直接调单节点；本服务是未来多节点扩展的预留。

---

## 入口与启动 (Entry Point)

- **入口文件**: `app/main.py`
- **运行命令**:
  ```bash
  cd services/asr-cluster
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python start.sh                  # 或 python -m app.main
  ```
- **默认监听**: `0.0.0.0:9100`
- **健康检查**: `GET /` — 返回 `{service, version, nodes_count}`

### 启动流程（main.py:24-29）
1. 启动 `HeartbeatMonitor`（asyncio 后台任务）
2. 打印 "ASR Cluster Manager started"

### 容器化（2026-07-12 后就绪）
- `Dockerfile` — 镜像构建
- `docker-compose.yml` — 独立 compose（与 mis-system 根 compose 分离）
- `.env.example` — 环境变量模板
- `.dockerignore` — 构建排除

```bash
cd services/asr-cluster
cp .env.example .env
docker compose up -d
```

---

## 对外接口 (External Interfaces)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务信息 + 节点数 |
| GET | `/nodes` | 列出所有节点状态（含 current_tasks / priority / status） |
| POST | `/nodes/register` | 注册新节点 |
| DELETE | `/nodes/{node_id}` | 注销节点 |
| POST | `/transcribe` | **集群转写**：自动选最优节点 |

### POST /nodes/register
**请求体**:
```json
{
  "id": "mlx-mac-m5",
  "url": "http://100.88.88.34:9000",
  "api_key": "kk-mis-asr-local-dev-key-2026",
  "model": "mlx-community/whisper-large-v3-turbo",
  "priority": 0,
  "max_concurrent": 2
}
```

**响应**:
```json
{
  "success": true,
  "message": "Node mlx-mac-m5 registered",
  "node": { "id": "...", "url": "...", "status": "...", ... }
}
```

### POST /transcribe（query 参数）
- `audio_path`: 服务端音频文件路径（节点共享文件系统的场景）
- `language`: 语言代码
- 自动挑最优节点 → 转发到 `node.url/transcribe` → 返回结果

**注意**：当前实现要求节点能直接访问 `audio_path`，仅适用于 NFS/共享存储场景。

---

## 关键依赖与配置 (Dependencies & Config)

### requirements.txt（2026-07-12 后已存在）
```
fastapi>=0.110
uvicorn[standard]>=0.30
pydantic>=2.6
httpx>=0.27
```

### 节点默认配置（app/nodes.py::get_registry）
首次启动自动注册 Mac 默认节点：
```python
ASRNode(
    id="mlx-mac-m5",
    url=os.getenv("DEFAULT_ASR_NODE_URL", "http://100.88.88.34:9000"),
    api_key=os.getenv("MLX_ASR_API_KEY", "kk-mis-asr-local-dev-key-2026"),
    model="mlx-community/belle-whisper-large-v3-zh-punct-fp16",
    priority=0,
    max_concurrent=2,
    status=NodeStatus.OFFLINE,  # 等首次心跳确认
)
```

### 心跳监控参数
- `interval=10.0s`（心跳间隔）
- `timeout=30.0s`（超时下线）
- `httpx.AsyncClient(timeout=5.0)`（单次检查超时）

---

## 数据模型 (Data Models)

### ASRNode（app/nodes.py，dataclass）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一标识 |
| url | str | base URL |
| api_key | str | 节点 API Key |
| model | str | 节点加载的模型 |
| priority | int | 调度优先级（0=最高） |
| max_concurrent | int | 最大并发 |
| status | NodeStatus | OFFLINE/HEALTHY/BUSY/DEGRADED |
| current_tasks | int | 当前任务数 |
| total_processed | int | 累计完成任务数 |
| last_heartbeat | float | 时间戳 |
| last_error | str \| None | 最近错误 |

`is_available` 属性：`status == HEALTHY AND current_tasks < max_concurrent`

### NodeStatus 枚举
- `OFFLINE` — 心跳失败 / 未注册
- `HEALTHY` — 心跳 OK 且未满载
- `BUSY` — 满载（current_tasks >= max_concurrent）
- `DEGRADED` — 任务失败标记

---

## 核心组件 (Core Components)

### NodeRegistry（app/nodes.py）
- `register(node)` / `deregister(node_id)`
- `get(node_id)` / `list_all()` / `list_available()`

### HeartbeatMonitor
- `start()` / `stop()` — 控制后台 asyncio 任务
- `_check_all()` 并发查所有节点 `/health`
- 单个节点 `status_code == 200` → 标 `HEALTHY`（若非 BUSY）
- 否则 → `DEGRADED` 或 `OFFLINE`

### LoadBalancer
- `pick()` — 返回 `(priority ASC, current_tasks ASC)` 排序的第一个可用节点
- `release(node)` — `current_tasks -= 1`，`total_processed += 1`

### ASRClient（app/client.py）
- `transcribe(audio_path, language, beam_size)` — 选节点 → 调 `/transcribe` → 异常时 `release` + 标 `DEGRADED`
- 返回结果带 `_node_id` 标记，便于排查
- 失败节点状态不重置（避免覆盖 `DEGRADED`）

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-13 续跑更新）
- ✅ pytest 已配置（2026-07-12 后补齐），2 文件全过：
  - `tests/test_security.py` — API Key 校验（缺/错 → 401）
  - `tests/integration/test_cluster.py` — 集群注册/心跳/负载均衡

### 运行
```bash
cd services/asr-cluster
PYTHONPATH=. pytest tests/ -v
```

### 手动 smoke test
```bash
# 启动后
curl http://localhost:9100/
curl http://localhost:9100/nodes
# 注册节点
curl -X POST http://localhost:9100/nodes/register \
  -H "Content-Type: application/json" \
  -d '{"id":"test","url":"http://localhost:9000","api_key":"kk-mis-asr-local-dev-key-2026"}'
```

---

## 常见问题 (FAQ)

**Q1: 节点一直是 OFFLINE？**
A: 检查节点 URL 是否可达；检查 `X-API-Key` 是否正确（cluster 调 `/health` 不带 key，但 `_check_node` 会带 key）。

**Q2: 节点被标 DEGRADED 后能恢复吗？**
A: 下次心跳 OK 会自动恢复 HEALTHY（见 `app/client.py` 的 `finally` 逻辑）。

**Q3: 为什么 meeting-notes 不走本集群？**
A: 当前实现要求节点共享文件系统（`audio_path` 直接传）。meeting-notes 走的是直接 HTTP 上传音频流的简化路径，更适合云原生场景。

**Q4: 怎么接入生产？**
A: 部署多个 mlx-asr 实例 → 在 asr-cluster 注册 → 改造 meeting-notes 的 `asr_client.py` 改调集群 `/transcribe`。

**Q5: 容器化了吗？**
A: ✅ 已就绪。`Dockerfile` + `docker-compose.yml` + `.env.example` + `.dockerignore` 均存在（2026-07-12 后补齐）。`docker compose up -d` 即可启动。

---

## 相关文件清单 (Key Files)

### 应用骨架
- `app/main.py` — FastAPI app + register/deregister/transcribe 端点
- `app/nodes.py` — NodeRegistry + HeartbeatMonitor + LoadBalancer + ASRNode dataclass
- `app/client.py` — ASRClient（任务分发器）

### 启动脚本
- `start.sh`

### 容器化
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.dockerignore`

### 测试（tests/）
- `test_security.py` — API Key 校验
- `integration/test_cluster.py` — 集群集成

---

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑：修正面包屑路径；修正 requirements.txt 已存在；修正测试已配 pytest（2 文件）；补容器化说明；修正 FAQ Q5
- 2026-07-12 15:55:11 — 初始化模块文档
