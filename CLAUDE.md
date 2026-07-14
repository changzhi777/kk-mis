[根目录](../CLAUDE.md) > **mis-system**

# kk-CMS · 企业 MIS 管理系统

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：
  - **面包屑路径修正**：原 `[根目录](../../CLAUDE.md)` 从本文件出发实际指向 `services/` 而非仓库根，已改为 `[根目录](../CLAUDE.md)`（本文件位于 `mis-system/`，`../` 即仓库根）；
  - **Mermaid 拓扑补 infra 外部引用节点**（`../infra/`，仓库根部署配置，被 .gitignore 忽略）；
  - **修正 infra 描述**：原"infra/ 位于仓库外"不准确，实际位于仓库根（`../infra/` 相对本目录），被根 .gitignore 忽略；
  - **修正测试段**：admin 测试从"24/24"更新为"12+ 文件含 integration/e2e/performance"；前端从"暂未配 Vitest"更新为"vitest 2.1.9 + 30 passed"；补 meeting-notes（3 文件）与 asr-cluster（2 文件）测试状态；
  - **修正"下一步建议"**：原"前端测试补齐"与"asr-cluster 容器化"均已完成，替换为新建议。
- 2026-07-12 16:08:16 — 仓库根 CLAUDE.md 续跑：本目录已被仓库根文档 `../CLAUDE.md` 索引定位，本文件聚焦代码项目本身。
- 2026-07-12 15:55:11 — 初始化 AI 上下文（zcf:init-project），生成根级与 5 个模块级 CLAUDE.md。

---

## 项目愿景 (Vision)

kk-cms 是一套面向中小型企业的 **一体化管理 SaaS 系统**，通过单一平台统一管理会议纪要、企业组织、财务收支、卡券资产、代理分销与 OA 办公，消除系统割裂与数据孤岛，降低管理成本。

核心价值主张：
- **AI 驱动**：会议录音一键转写 + LLM 智能整理，沉淀决策与行动项
- **一体化**：6 大模块共享 RBAC、JWT、审计日志、统一导航
- **开箱即用**：Teal 湖青主题前端 + FastAPI 后端 + PostgreSQL，生产可部署

---

## 架构总览 (Architecture)

### 模块结构图 (Mermaid)

```mermaid
graph TD
    Root["(根) kk-cms · MIS 系统"] --> Apps["apps"]
    Root --> Services["services"]
    Root -.部署配置.-> InfraExt["../infra/<br/>(仓库根, .gitignore 忽略)"]

    Apps --> Web["web<br/>(Vue3 前端 :5173)"]

    Services --> Admin["admin<br/>(企业管理 + 财务 + 资产 + 代理 + OA, :8300)"]
    Services --> MN["meeting-notes<br/>(会议纪要主应用, :8200)"]
    Services --> MLX["mlx-asr<br/>(Mac 本地 ASR 节点, :9000)"]
    Services --> Cluster["asr-cluster<br/>(ASR 集群管理, :9100)"]

    Admin -.uses.-> PG[("PostgreSQL<br/>kk_cms")]
    MN -.uses.-> PG
    Admin -.uses.-> Redis[("Redis")]
    MN -.uses.-> Redis

    MN -- "ASR Cluster API" --> Cluster
    Cluster -- "load balance" --> MLX

    MN -- "GLM / minimax / oMLX" --> LLM[("LLM 供应商")]
    Web -- "HTTPS / /oa/" --> Nginx["Nginx<br/>aisport.tech"]
    Nginx -- "/oa/api/*" --> MN
    Nginx -- "/oa/admin/*" --> Admin
    Nginx -- "/oa/assets/*" --> Web

    InfraExt -.管理.-> Nginx
    InfraExt -.systemd.-> Admin
    InfraExt -.systemd.-> MN
    InfraExt -.systemd.-> Cluster

    click Web "./apps/web/CLAUDE.md" "查看 web 模块文档"
    click Admin "./services/admin/CLAUDE.md" "查看 admin 模块文档"
    click MN "./services/meeting-notes/CLAUDE.md" "查看 meeting-notes 模块文档"
    click MLX "./services/mlx-asr/CLAUDE.md" "查看 mlx-asr 模块文档"
    click Cluster "./services/asr-cluster/CLAUDE.md" "查看 asr-cluster 模块文档"
```

### 数据流 (Data Flow)

1. **浏览器** → `https://aisport.tech/oa/` → **Nginx**（内联配置，反代 `/oa/api/*`、`/oa/admin/*`、`/oa/assets/*`）
2. **Nginx** → **FastAPI 服务**（meeting-notes :8200 / admin :8300）
3. **meeting-notes** → **asr-cluster (:9100)** 自动负载均衡到 **mlx-asr (:9000)** Mac 本地节点（Tailscale 100.88.88.x 内网）
4. **meeting-notes** → **LLM**（智谱 GLM-4.7 / minimax / 本地 oMLX）
5. **admin + meeting-notes** → **PostgreSQL**（`kk_cms` 库，postgres 用户）+ **Redis**

### 部署拓扑（生产）

- 域名：`aisport.tech`（SSL 由 Caddy 提供，Nginx 监听 80/443 反代 `/oa/*`）
- 进程管理：systemd（`kk-mis-meeting-notes.service` / `kk-mis-admin.service` / `kk-mis-asr-cluster.service`，配置位于仓库根 `../infra/systemd/`）
- Nginx 配置：`../infra/nginx/kk-cms.conf`（会议纪要 + ASR 集群）+ `kk-cms-admin.conf`（admin）
- 运维脚本：`../infra/scripts/`（backup_pg / health_check / reconcile，crontab 调度）
- 网络：Tailscale VPN 跨 Mac（开发机）与 Linux 服务器
- 部署方式：仓库根 `../infra/` 目录通过 `scp` 直传（GitHub 网络不稳，详见 project-mis-deploy.md）

---

## 模块索引 (Module Index)

| 模块 | 路径 | 端口 | 技术栈 | 一句话职责 |
|------|------|------|--------|------------|
| **web** | `apps/web/` | 5173 (dev) / 静态产物 | Vue 3.5 + TS + Element Plus + Vite | 6 大模块统一前端，Teal 湖青主题 |
| **admin** | `services/admin/` | 8300 | FastAPI + SQLAlchemy 2.0 async | 企业 RBAC + 财务 + 资产 + 代理 + OA 5 合 1 |
| **meeting-notes** | `services/meeting-notes/` | 8200 | FastAPI + SQLAlchemy async | 会议音频上传 → ASR → LLM 整理 |
| **mlx-asr** | `services/mlx-asr/` | 9000 | FastAPI + mlx-whisper | Mac 本地语音转写（Apple Silicon 优化） |
| **asr-cluster** | `services/asr-cluster/` | 9100 | FastAPI + httpx | 多 MLX 节点 ASR 集群注册与负载均衡 |

> ⚠️ `../infra/` 部署配置目录位于**仓库根**（相对本目录为 `../infra/`），含 systemd×3 + nginx×2 + scripts×3，被根 `.gitignore` 忽略，不进 Git。详见仓库根 `../CLAUDE.md` 的"部署配置目录"段。

---

## 技术栈 (Tech Stack)

### 后端（Python）
- **Web 框架**: FastAPI ≥ 0.110 + uvicorn[standard]
- **ORM**: SQLAlchemy 2.0 async + asyncpg（PG）/ aiosqlite（开发）
- **数据校验**: Pydantic ≥ 2.5 + pydantic-settings
- **认证**: PyJWT（access 2h / refresh 7d）+ bcrypt
- **HTTP 客户端**: httpx（OAuth + ASR 调用）
- **LLM**: 智谱 GLM-4.7 / minimax / 本地 oMLX（OpenAI 兼容）
- **可靠性**: tenacity 重试、uvicorn[standard]（HTTP/2）

### 前端（Vue3）
- **框架**: Vue 3.5 + TypeScript 5.6 + Vite 5.4
- **UI 库**: Element Plus 2.8（按需引入，bundle 减小 63%）
- **状态管理**: Pinia 2.2
- **路由**: Vue Router 4.4（`createWebHistory('/oa/')`，base 路径）
- **图表**: ECharts 6.1
- **HTTP**: axios 1.7（拦截器：401 自动清登录态）

### 数据库 / 缓存
- **PostgreSQL**（生产）：库名 `kk_cms`，用户 `postgres`（注意：非 `kk_cms`）
- **Redis**：admin 用 DB 1，meeting-notes 用 DB 0
- **SQLite**（开发）：`./storage/admin.db` / `./storage/kk_cms.db`

### AI / ASR
- **ASR**: Mac 本地 MLX Whisper（`mlx-community/belle-whisper-large-v3-zh-punct-fp16`）
- **LLM**: 智谱 GLM-4.7（默认）/ minimax MiniMax-Text-01 / 本地 oMLX（`gemma-4-e4b-it-4bit`）

---

## 运行与开发 (Run & Dev)

### 一键启动（开发模式）

```bash
# 1. 后端 — meeting-notes（端口 8200）
cd services/meeting-notes
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main

# 2. 后端 — admin（端口 8300）
cd services/admin
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main

# 3. 后端 — mlx-asr（端口 9000，仅 Mac）
cd services/mlx-asr
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main

# 4. 后端 — asr-cluster（端口 9100）
cd services/asr-cluster
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python start.sh

# 5. 前端 — web（端口 5173）
cd apps/web
pnpm install
pnpm dev
```

### Docker 一键启动（全栈 dev）

```bash
# mis-system/docker-compose.yml（admin + meeting-notes）
cp services/admin/.env.example services/admin/.env
cp services/meeting-notes/.env.example services/meeting-notes/.env
docker compose up -d
```

> asr-cluster 单独 compose（`services/asr-cluster/docker-compose.yml`），mlx-asr 仅 Mac 裸进程。

### 环境变量要点

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_DRIVER` | `sqlite` | 生产改为 `postgres` |
| `POSTGRES_HOST` | `127.0.0.1` | |
| `POSTGRES_USER` | `postgres` | ⚠️ 不是 `kk_cms` |
| `POSTGRES_DB` | `kk_cms`（meeting-notes）/ `kk_admin`（admin） | |
| `JWT_SECRET` | `kk-cms-jwt-secret-change-in-prod` | 两服务必须一致 |
| `GLM_API_KEY` | 空 | 智谱 GLM API Key |
| `MLX_ASR_API_KEY` | `kk-cms-asr-local-dev-key-2026` | meeting-notes 与 mlx-asr 必须一致 |
| `DEFAULT_ASR_NODE_URL` | `http://100.88.88.34:9000` | Tailscale Mac 内网 |
| `INIT_ADMIN_USERNAME` | `admin` | 首次启动自动 seed |
| `INIT_ADMIN_PASSWORD` | `admin123` | ⚠️ 生产必改 |

---

## 测试策略 (Testing)

### 测试全景（2026-07-13 续跑更新）

截至 2026-07-13，全系统共 **476 passed + 5 pre-existing**（含 2026-07-13 后补齐的 mlx-asr 13 + 前端 agent UI 16 测试；详见 memory `project-comprehensive-test-2026-07-13.md`），含跨服务集成 + E2E + 性能基线（locust，P95 < 2000ms）。

### 后端 pytest（admin）

```bash
cd services/admin
PYTHONPATH=. pytest tests/ -v
```

**当前状态**: 12+ 单元测试文件 + integration + e2e + performance，全过：
- `test_auth.py` — 登录/注册/token/密码/越权（防 RBAC 截断 bug 回归）
- `test_oa.py` — 公告/请假/报销/汇报/考勤 + 越权审批防护
- `test_asset.py` — 卡券类型/批次/核销
- `test_agent.py` — 区域代理/订单/双层返佣
- `test_finance.py` — 财务收支/账户/科目/报表
- `test_pricing.py` — VIP 阶梯折扣报价
- `test_vip_orders.py` — VIP 订单全流程
- `test_yearly_commission.py` — 年度累计返佣结算
- `test_anticounterfeit.py` — 防伪核销
- `test_config_validation.py` — 配置校验
- `test_auth_oauth.py` — OAuth 流程（待 GitHub 凭证启用）
- `test_oa_agent_bridge.py` — OA 与代理联动
- `integration/test_bridge_integration.py` — 跨域集成
- `e2e/test_vip_full_flow.py` — VIP 端到端
- `performance/locustfile.py` — 性能基线（P95 < 2000ms）
- `tests/REPORT.md` — 测试报告

### 后端 pytest（meeting-notes）

```bash
cd services/meeting-notes
PYTHONPATH=. pytest tests/ -v
```

**当前状态**: 3 文件全过（2026-07-12 后补齐）：
- `test_status_machine.py` — 会议状态机（uploaded→transcribing→completed/failed）
- `test_safe_filename.py` — 路径遍历防护
- `test_upload_security.py` — 上传安全校验

### 后端 pytest（asr-cluster）

```bash
cd services/asr-cluster
PYTHONPATH=. pytest tests/ -v
```

**当前状态**: 2 文件全过（2026-07-12 后补齐）：
- `test_security.py` — API Key 校验
- `integration/test_cluster.py` — 集群注册/心跳/负载均衡

### 后端（mlx-asr）

✅ pytest 已配置（2026-07-13 补齐），13 测试全过：mock `MLXTranscriber.transcribe` + API Key 401 + 文件大小 413 + `_safe_filename` 路径遍历防护（5 测试）。详见 `services/mlx-asr/CLAUDE.md`。

### 前端 vitest（apps/web）

```bash
cd apps/web
pnpm test          # run 模式
pnpm test:coverage # 覆盖率
```

**当前状态**: vitest 2.1.9 + jsdom + @vue/test-utils，46 个全过（含 agent UI API 层 + 状态映射 16 新增）：
- `stores/user` — RBAC 权限判断
- `router/guard` — 路由守卫
- `views/detail-export` — Markdown 导出
- `views/render-md` — XSS 防护（DOMPurify）
- `api/admin-agent` — agent API 方法（payOrder/completeOrder/commissionSummary/settleCommission）+ resource CRUD（mock axios）
- `views/agent-status-helpers` — OrderList/Commission 状态映射纯函数

### 测试基础设施
- 后端：SQLite 内存库（`./test.db`），自动清理；`tests/conftest.py` 提供 `client` + `auth_header`
- 前端：`environment: 'jsdom'`（happy-dom 与 DOMPurify 不兼容，已改 jsdom）

---

## 编码规范 (Coding Conventions)

### Python
- **类型注解**: 必须（`def foo(x: int) -> str:`）
- **异步**: 一律 `async def`，避免阻塞 I/O
- **命名**: 路由模块 `routes/<domain>.py`，模型 `models/<domain>.py`，schema `schemas/<domain>.py`
- **错误**: 用 `HTTPException(status_code=xxx, detail="...")`，不要 return dict
- **依赖注入**: 路由签名 `Depends(get_session)` / `Depends(get_current_user)`
- **SQLAlchemy**: 主键用 `BigInteger().with_variant(Integer, "sqlite")` 兼容 SQLite/PG

### Vue3 / TS
- **组合式 API**: 一律 `<script setup lang="ts">`
- **自动导入**: 通过 `unplugin-auto-import` + `unplugin-vue-components`，**禁止**手写 `import { ref } from 'vue'`（除非 vite 配置异常）
- **路径别名**: `@/` → `src/`
- **API 客户端**: `src/api/admin.ts` / `src/api/meetings.ts`（已封装 axios + JWT 拦截 + 401 跳登录）
- **Store**: Pinia setup 风格（`defineStore('user', () => { ... })`）
- **样式**: Sass + Element Plus 主题覆盖（Teal 湖青 `#0d9488`）
- **路由 base**: `createWebHistory('/oa/')`，所有 menu 路径用 `/dashboard` 而非 `/oa/dashboard`

### 提交规范（建议）
- `feat:` 新功能 / `fix:` bug / `refactor:` 重构 / `docs:` 文档 / `test:` 测试 / `chore:` 杂项
- 一个 commit 一个主题，避免巨型 commit

---

## AI 使用指引 (AI Guidance)

### 对 Claude 的指令优先级
1. **本 `CLAUDE.md` 是项目级 SOP**，子模块 CLAUDE.md 是它的细化
2. **项目记忆** (`memory/project-mis-*.md`) 是历史与决策的**真相源**，覆盖 CLAUDE.md 时优先采纳 memory
3. **代码与本文件冲突时，以代码为准**（CLAUDE.md 可能有滞后）

### 已知陷阱与边界
- **OAuth 第三方登录代码已就绪** (`services/admin/app/oauth/`)，但 GitHub Credentials 暂未启用，OAuth 路由会返回 503
- **asr-cluster** 默认注册 Mac 节点（`mlx-mac-m5`，Tailscale 内网），其他环境需修改 `services/asr-cluster/app/nodes.py` 的 `get_registry()` 默认值
- **生产数据库用户是 `postgres`**，不是 `kk_cms`（容易踩坑）
- **前端 base 是 `/oa/`**，所有路由跳转、内部 API 调用都用相对路径
- **JWT secret 必须一致**：admin 与 meeting-notes 共享同一个 `JWT_SECRET`，否则跨服务 token 验证失败
- **RBAC 权限码曾有截断 bug**（首字符缺失），见 `tests/test_auth.py::test_register_new_user` 回归测试，禁止删除
- **代理销售 2026-07-13 重构**：原 3 级分销已推翻，改为区域代理（按 region_code 平级）+ 双层返佣（单次数量折扣 + 年度累计阶梯），见 `docs/PRICING.md`

### 安全审计备忘
- 2026-07 真实多角色测试发现 **3 个潜伏 bug**：路由双 `oa/`、权限码首字符截断、审批越权，全部已修复 + 写回归测试
- 教训：**admin 单用户测试 ≠ 系统通过**，新增 RBAC 特性必须走端到端权限矩阵

### 高频任务速查
| 任务 | 入口 |
|------|------|
| 新增菜单 + 权限 | `services/admin/app/seed.py::_DEFAULT_MENUS` + `apps/web/src/router/index.ts` + 前端 view 文件 |
| 新增财务科目 | `services/admin/app/seed.py::_DEFAULT_CATEGORIES` |
| 新增审批流程 | `services/admin/app/seed.py`（leave/expense 各一条，可动态扩展） |
| 新增 LLM provider | `services/meeting-notes/app/services/llm.py::LLMClient.__init__` + `list_providers()` |
| 新增 ASR 节点 | POST `/nodes/register` to asr-cluster (:9100) |

---

## 当前状态指针 (Status Pointers)

详细历史决策与状态见项目记忆：

- `~/.claude/projects/-Users-mac-Documents-Claude-Projects-szdhts-a/memory/MEMORY.md` — 记忆索引
- `project-mis-overview.md` — MIS 项目总览（6 模块全上线 + OA5 + 注册向导 + 导出矩阵 + OAuth）
- `project-mis-deploy.md` — 线上部署架构（两服务 :8200/:8300，scp 直传模式）
- `project-mis-frontend-redesign.md` — 前端 UI 重设计（Teal 湖青 #0d9488，全完成）
- `project-mis-rbac-audit.md` — RBAC 安全审计（3 bug + 教训）
- `project-mis-decisions.md` — 决策清单（5 项定案 + 区域代理重构）
- `project-mis-4modules-launch.md` — 4 模块启动（合规防护 + 测试补齐）
- `project-comprehensive-test-2026-07-13.md` — 全面测试（447 passed + 性能基线）
- `reference-mis-oss.md` — 开源参考项目链接

---

## 下一步建议 (Next Steps)

> 原建议（前端测试 / asr-cluster 容器化 / mlx-asr 测试 / CI/CD）均已完成（2026-07-13）。

1. **API 文档聚合**：admin + meeting-notes 各自 `/docs`，考虑用 nginx 聚合到 `/oa/docs/`
2. **infra/ 版本化**：`../infra/` 被 .gitignore 忽略，含 nginx X-API-Key 占位，建议用私有仓库或 secrets 管理
3. **CI 扩展**：当前 CI（`.github/workflows/ci.yml`）跑 unit（忽略 integration/e2e/performance），后续可加 integration（装 requests）+ e2e + locust 性能基准
