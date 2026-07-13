[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [services](../) > **admin**

# services/admin · 企业管理 + 财务 + 资产 + 代理 + OA

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/services/` 而非仓库根，改为 `../../../CLAUDE.md`；[mis-system] 链接改为 `../../CLAUDE.md`）；测试全景已由 `mis-system/CLAUDE.md` 统一更新为"12+ 单元 + integration/e2e/performance"（详见 mis-system/CLAUDE.md 测试策略段，本模块对外接口/数据模型内容保持）；代理销售已重构为区域代理+双层返佣（2026-07-13，详见下方第 5 节）。
- 2026-07-12 16:08:16 — 续跑增量（zcf:init-project）：面包屑加深到 3 级（仓库根 → mis-system → services → admin），内容保持。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-mis` 后端的**一站式管理 API**，承载 5 大业务域（企业管理 + 财务 + 资产 + 代理 + OA），共用一套 RBAC 权限、JWT 认证、审计日志。所有路由统一加 `/admin` 前缀，便于 nginx 与 meeting-notes 的 `/api` 区分。

业务域拆分：
- **企业管理**（system）：用户/角色/权限(树形)/部门 + JWT + 动态菜单 + 审计
- **财务管理**（finance）：账户/科目/收支流水/ECharts 报表
- **资产管理**（asset）：卡券类型(VIP/代金券/兑换/储值 4 类) → 批次 → 卡券 → 核销
- **代理销售**（agent）：**区域代理（按 region_code 平级划分销售范围）+ 双层返佣（单次数量折扣 + 年度累计阶梯）**（2026-07-13 推翻原 3 级分销，避免合规边界）
- **OA 办公**（oa）：公告 / 请假 / 报销 / 审批中心 / 工作汇报 / 考勤

---

## 入口与启动 (Entry Point)

- **入口文件**: `app/main.py`
- **运行命令**:
  ```bash
  cd services/admin
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python -m app.main
  ```
- **默认监听**: `0.0.0.0:8300`（`APP_HOST` / `APP_PORT` 可改）
- **健康检查**: `GET /health`
- **OpenAPI 文档**: `GET /docs`

### 生命周期（main.py:21-35）
启动时 `init_db()` 自动建表 + seed 初始数据（admin 用户 + 默认菜单权限 + 财务科目 + 默认审批流程）。失败不阻塞，可后续重试。

---

## 对外接口 (External Interfaces)

所有路由挂在 `/admin` 前缀下（main.py:60-61），子前缀 `/api/v1/<domain>`。

> 📋 **精确接口清单**：112 个端点的完整「方法 / 路径 / 请求体模型 / 响应模型 / 权限码」矩阵见 [`docs/API_MATRIX.md`](docs/API_MATRIX.md)；下表为粗粒度概览。

### 1. 认证（auth + auth_oauth）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/api/v1/auth/login` | 登录，返回 access + refresh + user |
| POST | `/admin/api/v1/auth/register` | 自助注册（绑定 staff 角色） |
| POST | `/admin/api/v1/auth/refresh` | 刷新 token |
| GET | `/admin/api/v1/auth/me` | 当前用户信息 |
| GET | `/admin/api/v1/auth/menus` | 动态菜单树 |
| PUT | `/admin/api/v1/auth/password` | 改密 |
| POST | `/admin/api/v1/auth/logout` | 登出（前端清 token） |
| GET | `/admin/api/v1/auth/oauth/<provider>/authorize` | OAuth 跳转 |
| GET | `/admin/api/v1/auth/oauth/<provider>/callback` | OAuth 回调 |

OAuth providers：`github`（就绪待启用）/ `wechat`（预留）

### 2. 企业管理
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/users` | 用户管理 |
| CRUD | `/admin/api/v1/roles` | 角色管理 |
| GET | `/admin/api/v1/permissions/tree` / `/flat` | 权限树 / 扁平 |
| CRUD | `/admin/api/v1/departments` | 部门（树形） |
| GET | `/admin/api/v1/audit` | 审计日志（中间件自动写） |
| GET | `/admin/api/v1/dashboard` | 看板聚合 |

### 3. 财务管理
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/finance/accounts` | 账户 |
| CRUD | `/admin/api/v1/finance/categories` | 科目 |
| CRUD | `/admin/api/v1/finance/transactions` | 流水 |
| GET | `/admin/api/v1/finance/reports/summary` | 收支汇总 |
| GET | `/admin/api/v1/finance/reports/by-category` | 分类报表 |
| CSV | `/admin/api/v1/finance/reports/export` | 导出 |

### 4. 资产管理
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/asset/card-types` | 卡券类型 |
| CRUD | `/admin/api/v1/asset/batches` | 批次 |
| CRUD | `/admin/api/v1/asset/cards` | 卡券 |
| POST | `/admin/api/v1/asset/batches/{id}/generate` | 批量生成卡号 |
| POST | `/admin/api/v1/asset/cards/{id}/issue` | 发放 |
| POST | `/admin/api/v1/asset/cards/{id}/void` | 作废 |
| POST | `/admin/api/v1/asset/redemptions/redeem` | 核销 |

### 5. 代理销售（区域代理 + 双层返佣，2026-07-13 重构）

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/agent/agents` | 区域代理（按 `region_code` 划分） |
| GET | `/admin/api/v1/agent/orders/quote` | 实时折扣报价（不下单） |
| CRUD | `/admin/api/v1/agent/orders` | 订单（自动按 quantity 应用阶梯折扣） |
| CRUD | `/admin/api/v1/agent/commissions` | 单次返佣记录（兼容旧 level 字段） |
| GET | `/admin/api/v1/agent/commissions/summary` | 单次返佣汇总 |
| POST | `/admin/api/v1/agent/commissions/settle` | 单次返佣结算 |
| GET | `/admin/api/v1/agent/yearly-commission` | 年度累计返佣查询 |
| POST | `/admin/api/v1/agent/yearly-commission/settle` | 触发年度返佣结算（支持 dry_run） |
| POST | `/admin/api/v1/agent/orders/{id}/pay` | 订单付款 |
| POST | `/admin/api/v1/agent/orders/{id}/complete` | 订单完成 → 触发单次返佣 |

**核心规则**（详见 `docs/PRICING.md`）：
- VIP 单价 ¥1888，数量阶梯：1-99 张 7 折 / 100-999 张 6 折 / 1000+ 张 5 折
- 年度累计返佣：< 50 万 30% / 50-200 万 40% / > 200 万 50%
- 防伪：每张卡 64 位 `unique_code` + QR URL + mock `blockchain_tx_hash`（Phase 2 接 Fabric）

**核心服务**：
- `app/services/pricing.py`：`compute_vip_discount` + `compute_yearly_tier`
- `app/services/yearly_commission.py`：`settle_yearly_commissions` + `get_yearly_commissions`

### 5.1 防伪核销（公开访问）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/api/v1/asset/cards/verify/{unique_code}` | 防伪核销（无需登录，扫码直达） |

### 6. OA 办公
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/oa/announcements` | 公告 |
| POST | `/admin/api/v1/oa/announcements/{id}/publish` / `archive` | 发布/归档 |
| CRUD | `/admin/api/v1/oa/leaves` | 请假 |
| CRUD | `/admin/api/v1/oa/expenses` | 报销 |
| CRUD | `/admin/api/v1/oa/reports` | 工作汇报 |
| GET | `/admin/api/v1/oa/reports/all` | 全部（管理） |
| PUT | `/admin/api/v1/oa/reports/{id}/read` | 标已读 |
| POST | `/admin/api/v1/oa/approvals/instances/{id}/approve` / `reject` | 审批 |
| POST | `/admin/api/v1/oa/attendance/clock-in` / `clock-out` | 打卡 |
| GET | `/admin/api/v1/oa/attendance/today` / `me` / `stats` | 考勤 |

---

## 关键依赖与配置 (Dependencies & Config)

### requirements.txt
```
fastapi>=0.110
uvicorn[standard]>=0.30
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29          # PostgreSQL async driver
aiosqlite>=0.20        # SQLite 开发用
redis>=5.0
pydantic>=2.6
python-multipart>=0.0.9  # 文件上传
pyjwt>=2.8             # JWT
bcrypt>=4.0            # 密码哈希
httpx>=0.28            # OAuth 第三方 API
```

### 关键环境变量（app/config.py）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | 8300 | 监听端口 |
| `DB_DRIVER` | `sqlite` | 生产改 `postgres` |
| `POSTGRES_DB` | `kk_admin` | ⚠️ 与 meeting-notes 不同 |
| `POSTGRES_USER` | `postgres` | ⚠️ 不是 `kk_mis` |
| `REDIS_DB` | 1 | ⚠️ 与 meeting-notes（DB 0）分开 |
| `JWT_SECRET` | `kk-mis-jwt-secret-change-in-prod` | **必须与 meeting-notes 一致** |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE` | 7200 (2h) | |
| `REFRESH_TOKEN_EXPIRE` | 604800 (7d) | |
| `INIT_ADMIN_USERNAME` | `admin` | 首次启动 seed |
| `INIT_ADMIN_PASSWORD` | `admin123` | ⚠️ 生产必改 |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | 空 | OAuth（待启用） |

---

## 数据模型 (Data Models)

### SQLAlchemy 模型（app/models/）

| 文件 | 表 | 说明 |
|------|----|------|
| `base.py` | Base | 声明基类 |
| `enterprise.py` | users / roles / permissions / departments / user_roles / role_permissions | RBAC 核心 |
| `finance.py` | finance_accounts / finance_categories / finance_transactions | |
| `asset.py` | asset_card_types / asset_batches / asset_cards / asset_redemptions | 4 类型(VIP/代金/兑换/储值) |
| `agent.py` | agent_agent / agent_order / commission_record / yearly_commission | 区域代理 + 双层返佣（2026-07-13 重构） |
| `oa.py` | oa_announcement / oa_leave / oa_expense / oa_approval_instance / oa_report / oa_attendance | OA 6 表 |

> 代理模型 2026-07-13 重构：原 `level` 字段（3 级分销）保留兼容，新增 `region_code` + `yearly_commission` 表。详见 `docs/PRICING.md`。

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-13 续跑更新）
- ✅ pytest 全过，测试矩阵已大幅扩展（从原 5 文件 24 用例 → 12+ 单元 + integration + e2e + performance）
- 测试文件清单（`tests/`）：
  - **单元**：`test_auth.py` / `test_oa.py` / `test_finance.py` / `test_asset.py` / `test_agent.py` / `test_pricing.py` / `test_vip_orders.py` / `test_yearly_commission.py` / `test_anticounterfeit.py` / `test_config_validation.py` / `test_auth_oauth.py` / `test_oa_agent_bridge.py`
  - **集成**：`integration/test_bridge_integration.py`
  - **E2E**：`e2e/test_vip_full_flow.py`
  - **性能**：`performance/locustfile.py`（P95 < 2000ms 基线）+ `performance/README.md`
  - `tests/REPORT.md` — 测试报告
  - `tests/conftest.py` — `client` + `auth_header` fixtures

### 运行
```bash
cd services/admin
PYTHONPATH=. pytest tests/ -v
```

### 测试基础设施
- SQLite 内存库（`./test.db`），自动清理
- `conftest.py` 提供 `client`（session 级 TestClient）+ `auth_header`（登录拿 token）

---

## 常见问题 (FAQ)

**Q1: 生产数据库连接失败？**
A: 检查 `POSTGRES_USER` 是 `postgres` 而非 `kk_mis`；`POSTGRES_DB` 是 `kk_admin` 而非 `kk_mis`（与 meeting-notes 不同）。

**Q2: 跨服务 token 验证失败？**
A: admin 与 meeting-notes 必须共享同一个 `JWT_SECRET`。

**Q3: OAuth 路由 503？**
A: `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` 未配置，代码就绪但凭证待启用。

**Q4: 代理返佣计算异常？**
A: 2026-07-13 重构后，单次返佣按 `quantity` 阶梯折扣，年度返佣按累计金额阶梯；旧 `level` 字段保留兼容但不再用于计算。详见 `docs/PRICING.md`。

---

## 相关文件清单 (Key Files)

### 应用骨架
- `app/main.py` — FastAPI app + lifespan + init_db + seed
- `app/config.py` — Settings
- `app/db.py` — async engine + SessionLocal
- `app/security.py` — JWT + bcrypt + RBAC 依赖
- `app/seed.py` — 默认菜单/科目/审批流程 seed

### 路由（app/routes/，逐端点矩阵见 `docs/API_MATRIX.md`）
- `auth.py` / `auth_oauth.py` — 认证 + OAuth
- `users.py` / `roles.py` / `permissions.py` / `departments.py` / `audit.py` — 企业管理
- `finance/`（accounts / categories / transactions / reports）— 财务
- `asset/`（card_types / batches / cards / redemptions / verify）— 资产（含防伪核销）
- `agent/`（agents / orders / commissions / yearly_commission）— 区域代理 + 双层返佣
- `oa/`（announcements / approvals / leaves / expenses / reports / attendance）— OA 6 模块
- `oa_agent_bridge.py` — OA-Agent 桥接（`/oa-agent/*`，SSE 流式）

### 模型（app/models/）
- `base.py` / `enterprise.py` / `finance.py` / `asset.py` / `agent.py` / `oa.py`

### 服务（app/services/）
- `pricing.py` — VIP 阶梯折扣 + 年度返佣阶梯
- `yearly_commission.py` — 年度返佣结算

### 测试（tests/）
- 12+ 单元测试 + `integration/` + `e2e/` + `performance/` + `REPORT.md`

---

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑：修正面包屑路径；测试段更新为 12+ 文件含 integration/e2e/performance；补数据模型 oa.py + agent 重构说明
- 2026-07-12 16:08:16 — 续跑：面包屑加深到 3 级
- 2026-07-12 15:55:11 — 初始化模块文档
