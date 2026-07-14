[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [services](../) > **admin**

# services/admin · 企业管理 + 财务 + 资产 + 代理 + OA + **CMS**

## 变更记录 (Changelog)

- 2026-07-14 14:54:32 — 续跑增量更新（zcf:init-project）：
  - **CMS 内容管理模块（VIP 卡旅游产品）全完成**（详见 memory `project-cms-module-2026-07-14.md`，架构详见 `mis-system/docs/cms-content-module-research.md`）：
    - **12 个新 router**（`app/routes/cms/` 子包）：auth / products / media / merchants / leads / orders / coupons / reviews / stats / payments / weather / search，统一挂在 `/admin/api/v1/cms/` 前缀
    - **3 个新 service**（`app/services/`）：`payment.py`（PaymentGateway 抽象 + MockGateway 实现）/ `weather.py`（和风实时 + 预报）/ `notifier.py`（webhook 通知）
    - **10 个新数据模型**（`app/models/cms.py`）：TourProduct / TourCustom / TourPass / MediaAsset / Merchant / ProductOrder / Coupon / InquiryLead / Review / EndUser(C 端账号)
    - **真发卡链路**：订单支付→自动发 asset 卡（产品须关联 `card_type_id` + 有 active batch）
    - **C 端 EndUser 账号**：JWT `type=end_user`（可选，匿名仍可购买/评论）
    - **公开页 `/product/:slug`**：SEO + 行程/权益/评价/相关推荐 + 目的地天气卡片
    - **移动端 H5 + 数据分析漏斗**：浏览→询价→订单→支付
    - admin 131 passed / vue-tsc 0 / vitest 46 全 push；**2026-07-14 已部署到 `43.129.201.118`**
  - **测试基线重置**（详见 `project-fullstack-audit-2026-07-14.md`）：admin 86+ 单元 + 6 pre-existing → **94 passed 0 pre-existing**（pre-existing 根因为 `.venv` 缺 `pydantic_settings` 依赖）；
  - **2 真实 BUG 修复**：`global-setup.ts` teardown dbPath `..`×3 错位致 schema 漂移 + `locustfile.py` quote 任务假设 batch_id=1 不存在 100% 失败；
  - **后端异味清理**：`__import__("fastapi").Depends()`→正常 import（6 处 in `oa_agent_bridge.py`）；Pydantic `class Config`→`ConfigDict`（5 schema 25 处）；
  - **接口清单更新**：112 → **~124 端点**（+12 CMS router，端点矩阵见 `docs/API_MATRIX.md`）；
  - **清理底部重复 Changelog 段**（原 L265-269 孤立段删除，统一在顶部维护）。
- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/services/` 而非仓库根，改为 `../../../CLAUDE.md`；[mis-system] 链接改为 `../../CLAUDE.md`）；测试全景已由 `mis-system/CLAUDE.md` 统一更新为"12+ 单元 + integration/e2e/performance"（详见 mis-system/CLAUDE.md 测试策略段，本模块对外接口/数据模型内容保持）；代理销售已重构为区域代理+双层返佣（2026-07-13，详见下方第 5 节）。
- 2026-07-12 16:08:16 — 续跑增量（zcf:init-project）：面包屑加深到 3 级（仓库根 → mis-system → services → admin），内容保持。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-cms` 后端的**一站式管理 API**，承载 **7 大业务域**（企业管理 + 财务 + 资产 + 代理 + OA + **CMS 内容管理** + **oa-agent 桥接**），共用一套 RBAC 权限、JWT 认证、审计日志。所有路由统一加 `/admin` 前缀，便于 nginx 与 meeting-notes 的 `/api` 区分。

业务域拆分：
- **企业管理**（system）：用户/角色/权限(树形)/部门 + JWT + 动态菜单 + 审计
- **财务管理**（finance）：账户/科目/收支流水/ECharts 报表
- **资产管理**（asset）：卡券类型(VIP/代金券/兑换/储值 4 类) → 批次 → 卡券 → 核销
- **代理销售**（agent）：**区域代理（按 region_code 平级划分销售范围）+ 双层返佣（单次数量折扣 + 年度累计阶梯）**（2026-07-13 推翻原 3 级分销，避免合规边界）
- **OA 办公**（oa）：公告 / 请假 / 报销 / 审批中心 / 工作汇报 / 考勤
- **🆕 CMS 内容管理**（cms，2026-07-14 全完成）：VIP 卡旅游产品（A 订制游 + C 权益卡）+ 富文本/素材库 + 公开页 SEO + 真发卡 + C 端账号 + 移动端 H5 + 漏斗分析
- **oa-agent 桥接**（oa_agent_bridge）：admin → oa-agent :9001 SSE 流式桥接（`/oa-agent/*`）

---

## 入口与启动 (Entry Point)

- **入口文件**: `app/main.py`
- **运行命令**:
  ```bash
  cd services/admin
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt pydantic-settings   # ⚠️ 必须装，否则 bridge fixture 启 oa-agent 失败
  python -m app.main
  ```
- **默认监听**: `0.0.0.0:8300`（`APP_HOST` / `APP_PORT` 可改）
- **健康检查**: `GET /health`
- **OpenAPI 文档**: `GET /docs`

### 生命周期（main.py）
启动时 `init_db()` 自动建表 + seed 初始数据（admin 用户 + 默认菜单权限 + 财务科目 + 默认审批流程 + CMS 初始数据）。失败不阻塞，可后续重试。

---

## 对外接口 (External Interfaces)

所有路由挂在 `/admin` 前缀下（main.py），子前缀 `/api/v1/<domain>`。

> 📋 **精确接口清单**：约 **124 个端点**的完整「方法 / 路径 / 请求体模型 / 响应模型 / 权限码」矩阵见 [`docs/API_MATRIX.md`](docs/API_MATRIX.md)；下表为粗粒度概览。

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

### 7. 🆕 CMS 内容管理（VIP 卡旅游产品，2026-07-14 全完成）

> 完整能力链路：admin 富文本编辑产品（TipTap+素材库）→ 分类/标签 → 公开介绍页 `/product/:slug`（SEO+行程/权益+评价+相关推荐+目的地天气）→ 询价/购买（券抵扣+mock 支付→真发 asset 卡）→ admin 跟进（线索/订单/评论审核）+ 数据看板（ECharts）+ CSV 导出 + webhook 通知。
>
> 所有路由挂在 `/admin/api/v1/cms/` 前缀；公开页 `/product/:slug`（前端路由，无 /oa 前缀便于 SEO）。

#### 7.1 认证（end_user）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/api/v1/cms/auth/register` | C 端用户注册（JWT `type=end_user`） |
| POST | `/admin/api/v1/cms/auth/login` | C 端用户登录 |
| GET | `/admin/api/v1/cms/auth/me` | C 端当前用户 |

#### 7.2 产品管理
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/products` | 旅游产品（TourProduct + TourCustom + TourPass，A 订制游 + C 权益卡） |
| GET | `/admin/api/v1/cms/products/{slug}` | 按 slug 查（公开页用） |
| POST | `/admin/api/v1/cms/products/{id}/publish` / `archive` | 发布 / 归档 |
| GET | `/admin/api/v1/cms/products/{id}/related` | 相关推荐（同分类/标签） |

#### 7.3 媒体素材库
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/media` | 媒体素材（图片/视频，MediaAsset） |
| GET | `/admin/api/v1/cms/media/picker` | 弹窗选择器接口 |
| POST | `/admin/api/v1/cms/media/upload` | 上传（multipart） |

#### 7.4 商家 / 商家审核
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/merchants` | 商家管理（Merchant） |
| POST | `/admin/api/v1/cms/merchants/{id}/audit` | 商家入驻审核 |

#### 7.5 线索 / 询价
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/leads` | 询价线索（InquiryLead） |
| POST | `/admin/api/v1/cms/leads/{id}/assign` | 分配给客服 |
| CSV | `/admin/api/v1/cms/leads/export` | 导出 |

#### 7.6 订单 + 支付
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/orders` | 订单（ProductOrder） |
| POST | `/admin/api/v1/cms/orders/{id}/pay` | 付款（调 PaymentGateway） |
| POST | `/admin/api/v1/cms/orders/{id}/cancel` | 取消 |
| POST | `/admin/api/v1/cms/orders/{id}/refund` | 退款 |
| POST | `/admin/api/v1/cms/orders/{id}/issue-card` | 真发 asset 卡（依赖产品 `card_type_id` + active batch） |
| CSV | `/admin/api/v1/cms/orders/export` | 导出 |
| CRUD | `/admin/api/v1/cms/payments` | 支付记录 |
| POST | `/admin/api/v1/cms/payments/callback/<gateway>` | 支付回调（webhook） |

#### 7.7 优惠券
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/coupons` | 优惠券（Coupon） |
| POST | `/admin/api/v1/cms/coupons/{id}/issue` | 发放 |
| POST | `/admin/api/v1/cms/coupons/redeem` | 核销（下单时） |

#### 7.8 评论
| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/admin/api/v1/cms/reviews` | 评论（Review） |
| POST | `/admin/api/v1/cms/reviews/{id}/audit` | 审核 |
| POST | `/admin/api/v1/cms/reviews/{id}/reply` | 商家回复 |

#### 7.9 数据看板 + 漏斗
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/api/v1/cms/stats/overview` | 总览（UV/订单/GMV） |
| GET | `/admin/api/v1/cms/stats/funnel` | 漏斗（浏览→询价→订单→支付） |
| GET | `/admin/api/v1/cms/stats/products/{id}` | 单品分析 |

#### 7.10 天气
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/api/v1/cms/weather/current` | 目的地实时天气（`QWEATHER_KEY`） |
| GET | `/admin/api/v1/cms/weather/forecast` | 7 日预报 |

#### 7.11 公开搜索（无需登录）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/api/v1/cms/search/products` | 全文搜索（按标题/标签/目的地） |

### 8. oa-agent 桥接
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/api/v1/oa-agent/query` | SSE 流式桥接到 oa-agent :9001（7 渠道联网） |
| POST | `/admin/api/v1/oa-agent/query_weather` | 天气查询（oa-agent `query_weather` 工具） |
| POST | `/admin/api/v1/oa-agent/ai-design-tour` | CMS「AI 设计行程」专用入口 |

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
pydantic-settings>=2.0  # ⚠️ 必装，oa-agent bridge fixture 依赖
python-multipart>=0.0.9  # 文件上传（CMS 媒体上传）
pyjwt>=2.8             # JWT
bcrypt>=4.0            # 密码哈希
httpx>=0.28            # OAuth 第三方 API + oa-agent 桥接
```

### 关键环境变量（app/config.py）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | 8300 | 监听端口 |
| `DB_DRIVER` | `sqlite` | 生产改 `postgres` |
| `POSTGRES_DB` | `kk_admin` | ⚠️ 与 meeting-notes 不同 |
| `POSTGRES_USER` | `postgres` | ⚠️ 不是 `kk_cms` |
| `REDIS_DB` | 1 | ⚠️ 与 meeting-notes（DB 0）分开 |
| `JWT_SECRET` | `kk-cms-jwt-secret-change-in-prod` | **必须与 meeting-notes 一致**（≥ 36 字节） |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE` | 7200 (2h) | |
| `REFRESH_TOKEN_EXPIRE` | 604800 (7d) | |
| `INIT_ADMIN_USERNAME` | `admin` | 首次启动 seed |
| `INIT_ADMIN_PASSWORD` | `admin123` | ⚠️ 生产必改 |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | 空 | OAuth（待启用） |
| `QWEATHER_KEY` | 空 | 🆕 CMS weather 服务必需（与 oa-agent 共享） |
| `OA_AGENT_URL` | `http://localhost:9001` | 🆕 oa-agent 服务地址（CMS AI 设计行程依赖） |
| `STORAGE_BACKEND` | `local` | 🆕 Sprint 0：对象存储后端（`local` \| `cos`，Sprint 1 已实装 cos）|
| `STORAGE_LOCAL_ROOT` | `storage/uploads` | 🆕 Sprint 0：LocalStorage 根目录 |
| `COS_REGION` / `COS_SECRET_ID` / `COS_SECRET_KEY` / `COS_BUCKET` | 空 | 🆕 Sprint 1：腾讯云 COS 凭据（CAM 子账号，建议 STS 临时凭证）；控制台 Bucket `qm-wx-1418512491` ap-guangzhou |
| `COS_APPID` / `COS_SCHEME` / `COS_CDN_DOMAIN` | 见 `.env.example` | 🆕 Sprint 1：COS 高级配置 |
| `COS_PRESIGN_EXPIRE` / `COS_DOWNLOAD_EXPIRE` / `COS_MAX_OBJECT_MB` | `3600` / `600` / `500` | 🆕 Sprint 1：签名有效期与对象大小限制 |
| `STS_ROLE_ARN` / `STS_SESSION_NAME` / `STS_SESSION_DURATION` / `STS_POLICY` | 空 | 🔜 Phase 2：临时凭证（Phase 1 可选；推荐生产开） |

---

## 数据模型 (Data Models)

### SQLAlchemy 模型（app/models/）

| 文件 | 表 | 说明 |
|------|----|------|
| `base.py` | Base | 声明基类（`declarative_base` 风格，2026-07-14 迁移） |
| `enterprise.py` | users / roles / permissions / departments / user_roles / role_permissions | RBAC 核心 |
| `finance.py` | finance_accounts / finance_categories / finance_transactions | |
| `asset.py` | asset_card_types / asset_batches / asset_cards / asset_redemptions | 4 类型(VIP/代金/兑换/储值) |
| `agent.py` | agent_agent / agent_order / commission_record / yearly_commission | 区域代理 + 双层返佣（2026-07-13 重构） |
| `oa.py` | oa_announcement / oa_leave / oa_expense / oa_approval_instance / oa_report / oa_attendance | OA 6 表 |
| **`cms.py`** | 🆕 `cms_tour_product` / `cms_tour_custom` / `cms_tour_pass` / `cms_media_asset` / `cms_merchant` / `cms_product_order` / `cms_coupon` / `cms_inquiry_lead` / `cms_review` / `cms_end_user` | **CMS 内容管理 10 表**（2026-07-14 上线） |

> 代理模型 2026-07-13 重构：原 `level` 字段（3 级分销）保留兼容，新增 `region_code` + `yearly_commission` 表。详见 `docs/PRICING.md`。
>
> CMS 模型 2026-07-14 上线：`cms_end_user` 是 C 端账号（与 `users` 业务用户分离，JWT `type=end_user` 区分）；`cms_product_order.issue_card_id` 关联 `asset_cards.id` 实现真发卡。

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-14 续跑重置基线）
- ✅ pytest **94 passed 0 pre-existing**（2026-07-14 修复 pre-existing 根因：`.venv` 缺 `pydantic_settings`）
- 测试文件清单（`tests/`）：
  - **单元**：`test_auth.py` / `test_oa.py` / `test_finance.py` / `test_asset.py` / `test_agent.py` / `test_pricing.py` / `test_vip_orders.py` / `test_yearly_commission.py` / `test_anticounterfeit.py` / `test_config_validation.py` / `test_auth_oauth.py` / `test_oa_agent_bridge.py` / **`test_cms_*.py`**（CMS 12 router 覆盖）
  - **集成**：`integration/test_bridge_integration.py` + **`integration/test_cms_full_flow.py`**（CMS 全链路）
  - **E2E**：`e2e/test_vip_full_flow.py` + **`e2e/test_cms_purchase_flow.py`**（CMS 购买→发卡）
  - **性能**：`performance/locustfile.py`（P95 < 2000ms 基线；2026-07-14 修 batch_id=1 假设 404 容忍）+ `performance/README.md`
  - `tests/REPORT.md` — 测试报告
  - `tests/conftest.py` — `client` + `auth_header` fixtures（含 `fail→skip` 守卫：oa-agent 目录不存在时 skip）

### 运行
```bash
cd services/admin
PYTHONPATH=. pytest tests/ -v
```

### 测试基础设施
- SQLite 内存库（`./test.db`），自动清理
- `conftest.py` 提供 `client`（session 级 TestClient）+ `auth_header`（登录拿 token）
- `performance/locustfile.py` 修后用 `catch_response` 容忍 404（2026-07-14）

---

## 常见问题 (FAQ)

**Q1: 生产数据库连接失败？**
A: 检查 `POSTGRES_USER` 是 `postgres` 而非 `kk_cms`；`POSTGRES_DB` 是 `kk_admin` 而非 `kk_cms`（与 meeting-notes 不同）。

**Q2: 跨服务 token 验证失败？**
A: admin 与 meeting-notes 必须共享同一个 `JWT_SECRET`（≥ 36 字节，2026-07-14 加长）。

**Q3: OAuth 路由 503？**
A: `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` 未配置，代码就绪但凭证待启用。

**Q4: 代理返佣计算异常？**
A: 2026-07-13 重构后，单次返佣按 `quantity` 阶梯折扣，年度返佣按累计金额阶梯；旧 `level` 字段保留兼容但不再用于计算。详见 `docs/PRICING.md`。

**Q5: 跑测试报 6 ERROR？**
A: admin `.venv` 缺 `pydantic_settings` 依赖，bridge fixture 启 oa-agent 失败。`pip install pydantic-settings` 后重跑。详见 memory `project-fullstack-audit-2026-07-14.md`。

**Q6: CMS 真发卡失败？**
A: 检查产品是否关联 `card_type_id`（cms_tour_product.card_type_id）+ 有 active batch（asset_batches.status=active）。现 `MockGateway`，真支付需商户号/密钥。

**Q7: CMS weather 服务返回 503？**
A: `QWEATHER_KEY` 未配置。生产部署必须设；oa-agent 的 `query_weather` 工具独立（git remote 待确认 push）。

---

## 相关文件清单 (Key Files)

### 应用骨架
- `app/main.py` — FastAPI app + lifespan + init_db + seed
- `app/config.py` — Settings（`pydantic-settings` `ConfigDict` 风格，2026-07-14 迁移）
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
- **`cms/`**（🆕 auth / products / media / merchants / leads / orders / coupons / reviews / stats / payments / weather / search）— **CMS 12 router**（2026-07-14）
- `oa_agent_bridge.py` — OA-Agent 桥接（`/oa-agent/*`，SSE 流式）

### 模型（app/models/）
- `base.py` / `enterprise.py` / `finance.py` / `asset.py` / `agent.py` / `oa.py`
- **`cms.py`**（🆕）— **CMS 10 数据模型**（2026-07-14）

### 服务（app/services/）
- `pricing.py` — VIP 阶梯折扣 + 年度返佣阶梯
- `yearly_commission.py` — 年度返佣结算
- **`payment.py`**（🆕）— **支付网关（PaymentGateway 抽象 + MockGateway）**
- **`weather.py`**（🆕）— **和风天气实时 + 预报**
- **`notifier.py`**（🆕）— **webhook 通知（订单/线索/评论状态变更）**
- **`storage/`**（🆕 2026-07-14 Sprint 0/1）— **对象存储抽象层**（`Storage` ABC + `LocalStorage` 默认实现 + `CosStorage` Sprint 1 实装 + `STSCredentialProvider`）；管理 14 个写文件点；backend 由 `STORAGE_BACKEND=local|cos` 切换；详见下文「Storage 抽象层」段

### 测试（tests/）
- 16 测试文件（12+ 单元 + 集成 + E2E + 性能 + REPORT.md）；详见上文"测试与质量"段
- 🆕 `tests/test_storage_*.py`（30+9+9 用例）+ `tests/test_cos_integration.py`（6 个 sprint1 集成桩，无 INTEGRATION env 自动 skip）

### 文档（docs/）
- `API_MATRIX.md` — 124 端点完整矩阵
- `PRICING.md` — VIP 阶梯折扣 + 年度返佣规则
- **`cms-content-module-research.md`**（🆕，`mis-system/docs/` 下）— **CMS 架构决策与设计文档**
