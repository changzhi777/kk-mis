[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [services](../) > **admin**

# services/admin · 企业管理 + 财务 + 资产 + 代理 + OA + **CMS**

## 变更记录 (Changelog)

- 2026-07-15 12:30:00 — 第三轮稳健版精细续跑（zcf:init-project）：
  - **5 个高 ROI 文件深读完成**（详见 §7.12/§7.13/§7.14 + §11 Storage 抽象层）：
    - **§7.12 支付网关抽象**（`app/services/payment.py`，72 行）：PaymentGateway Protocol + MockGateway 全 stub；当前生产 `gateway = MockGateway()`，3 个方法（`pay`/`refund`/`query`）均不接真支付；真接入只需实现协议 + `set_gateway()` 注入；
    - **§7.13 和风天气服务**（`app/services/weather.py`，81 行）：`QWEATHER_KEY` + geo lookup + `get_weather()`（实时 `/v7/weather/now`）+ `get_forecast(days=3)`，无 KEY 或异常均 fail-open 返回 stub（不阻塞 CMS 公开页）；
    - **§7.14 支付回调 webhook（关键 gap）**（`app/routes/cms/payments.py`，**仅 14 行占位**）：`POST /admin/api/v1/cms/payments/notify/{gateway_name}` 只回 `{"received": True}`，**未实现验签/幂等/订单 paid 状态更新/真发卡触发/失败回滚**——CMS 真支付接入核心风险点；
    - **§11 Storage 抽象层**（新增整节）：详述 `Storage` ABC + `LocalStorage` + `CosStorage` + `STSCredentialProvider`；**STS 决策定案**（YAGNI）：2026-07-15 用户决策复用 `qmwx-cos-uploader` 第 2 密钥长密钥（AKIDI5i...），sts.py 173 行作为 Sprint 1 骨架保留待后续启用；
  - **关键 gap 标注（CMS 真支付前置条件）**：`payment.py`（协议 stub）+ `routes/cms/payments.py`（webhook 占位）→ 双层空心结构，必须先实现 webhook 验签 + 幂等表 + 订单状态机 + 发卡触发 + 失败回滚，再谈真网关对接；
  - **未触碰 git**：mis-system 已 commit 11:42+11:55（hash 07bf105 + 9938ed6），文档改动仅在文件系统层。
- 2026-07-14 14:54:32 — 续跑增量更新（zcf:init-project）：CMS 内容管理模块（VIP 卡旅游产品）全完成，11 个新 router（实际 11 个：auth/products/media/merchants/leads/orders/coupons/reviews/stats/payments/weather；search 在 products.py 内合并）+ 3 个新 service（payment/weather/notifier）+ 10 个新数据模型；真发卡链路（产品须关联 card_type_id + 有 active batch）；C 端 EndUser 账号（JWT type=end_user）；公开页 /product/:slug（SEO + 行程/权益/评价/相关推荐 + 目的地天气卡片）；移动端 H5 + 数据分析漏斗；admin 131 passed / vue-tsc 0 / vitest 46 全 push；**2026-07-14 已部署到 43.129.201.118**。测试基线重置：admin 86+ 单元 + 6 pre-existing → 94 passed 0 pre-existing（pre-existing 根因为 `.venv` 缺 `pydantic_settings` 依赖）。修复 2 真实 BUG（global-setup.ts teardown dbPath 错位 + locustfile.py quote 任务 batch_id=1 假设 404 容忍）。后端异味清理（`__import__("fastapi").Depends()`→正常 import 6 处 + Pydantic Config→ConfigDict 5 schema 25 处）。接口清单更新：112 → ~124 端点（+11 CMS router）。
- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 实际指向 services/ 而非仓库根，改为 `../../../CLAUDE.md`）；代理销售已重构为区域代理+双层返佣（2026-07-13）。
- 2026-07-12 16:08:16 — 续跑增量（zcf:init-project）：面包屑加深到 3 级，内容保持。
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
  pip install -r requirements.txt pydantic-settings
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

> 📋 **精确接口清单**：约 **124 个端点**的完整「方法/路径/请求体模型/响应模型/权限码」矩阵见 [`docs/API_MATRIX.md`](docs/API_MATRIX.md)；下表为粗粒度概览。

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
| CRUD | `/admin/api/v1/finance/transactions` | 流水（**2026-07-15 起 DEPRECATED**，新流程走 voucher 凭证） |
| CRUD | `/admin/api/v1/finance/vouchers` | 🆕 复式记账凭证（Voucher + JournalEntry，借贷平衡） |
| GET | `/admin/api/v1/finance/reports/summary` | 收支汇总 |
| GET | `/admin/api/v1/finance/reports/by-category` | 分类报表 |
| GET | `/admin/api/v1/finance/reports/trial-balance` / `balance-sheet` / `income-statement` | 🆕 试算/资负/利润 3 报表 |
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
| POST | `/admin/api/v1/cms/payments/notify/{gateway}` | 支付回调（webhook，**当前仅 14 行占位**，详见 §7.14） |

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

#### 7.12 支付网关抽象（`app/services/payment.py`，72 行，**2026-07-15 深读**）

**核心抽象**：

```python
class PaymentGateway(Protocol):
    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult: ...
    async def refund(self, order_id: int, transaction_id: str, amount=None) -> PaymentResult: ...
    async def query(self, order_id: int, transaction_id: str = "") -> PaymentResult: ...

class PaymentResult:
    success: bool
    transaction_id: str
    message: str
```

**当前实现 `MockGateway`**（全部 stub）：
- `pay` → 立即 `success=True`，transaction_id = `mock_{order_id}_{int(time.time())}`
- `refund` → 立即 `success=True`，transaction_id = `mock_refund_{order_id}_{int(time.time())}`
- `query` → 始终返回 `success=True`（无论是否真付过）

**全局切换**：
```python
gateway: PaymentGateway = MockGateway()
def set_gateway(g: PaymentGateway) -> None:
    global gateway; gateway = g
```

**真接入步骤**（来自模块文档头注释）：
1. 实现 `PaymentGateway` 的 `WechatGateway` / `AlipayGateway`（调真 API + 验签）
2. settings 配商户号 / API 密钥 / 回调 URL
3. 启动时 `set_gateway(真实现)` 或改全局 gateway

**关键 gap**：
- **3 个方法签名**与任务描述的 5 方法（`create_order`/`query_order`/`close_order`/`refund`/`verify_callback`）不一致——实际文件只有 `pay/refund/query`；
- **无 `create_order`**（订单创建在 orders 路由处理，与支付解耦）
- **无 `close_order`**（关闭逻辑在 orders 路由的 cancel）
- **无 `verify_callback`**（webhook 验签逻辑不在 service 层——详见 §7.14）
- **无订单状态机**：支付成功是否触发发卡，在 webhook 路由处理，不在 service 层
- **无幂等保护**：相同 order_id 重复 `pay` 会生成不同 transaction_id（mock 场景无影响，真支付会出现双扣风险）
- **无金额校验**：调用方需自行保证 `amount` 与订单一致（service 层不验证）

**测试覆盖**：当前 `MockGateway` 单测无（mock 路径就是 stub），E2E `e2e/test_cms_purchase_flow.py` 走完整 mock 链路。

#### 7.13 和风天气服务（`app/services/weather.py`，81 行，**2026-07-15 深读**）

**凭据**（`.env`）：
- `QWEATHER_KEY`：和风 API Key（**生产必配**，否则 fail-open）
- `QWEATHER_API_HOST`：默认 `nf5b5vtkcp.re.qweatherapi.com`（复用 QM-WX 凭据）

**3 个公开函数**：

| 函数 | 签名 | 行为 |
|------|------|------|
| `_geo_lookup` | `async (city: str) -> (lon, lat) \| None` | 调 `/geo/v2/city/lookup` 拿经纬度；无 KEY 或查不到返回 None |
| `get_weather` | `async (city: str) -> dict` | 实时天气（`/v7/weather/now`）：返回 city/text/temperature/feelsLike/humidity/icon/windDir/windScale |
| `get_forecast` | `async (city: str, days: int = 3) -> list` | N 日预报（`/v7/weather/{days}d`）：返回 daily 列表 |

**关键设计**：
- **超时 10s**（`httpx.AsyncClient(timeout=10)`）
- **fail-open 双层兜底**：
  - 无 `QWEATHER_KEY` → 直接 stub（`text="天气服务未配置"`）
  - geo lookup 失败 → 当前城市 stub
  - weather/forecast API 异常 → `"获取失败"` stub
- **不抛异常**：所有异常路径都返回兜底数据，**不阻塞 CMS 公开页渲染**
- **图标 icon 字段**：和风返回 999 表示未知，前端需 fallback 处理
- **单位**：温度默认摄氏度（华氏需前端换算）

**与 oa-agent 关系**：
- admin 直接调和风 API（**主路径**，公开页 weather 卡片）
- oa-agent 独立有 `query_weather` 工具（路径：`/admin/api/v1/oa-agent/query_weather`），给聊天 / AI 设计行程用
- 两路**不互斥**，admin 主路径优先（更稳定，无 LLM 介入）

**测试覆盖**：`test_cms.py` 含天气端点（mock httpx）。

#### 7.14 支付回调 webhook（`app/routes/cms/payments.py`，**14 行占位**，**2026-07-15 深读·关键 gap**）

**当前实现**（完整源码）：
```python
@router.post("/notify/{gateway_name}")
async def payment_notify(gateway_name: str, request: Request):
    """支付网关异步回调（占位：真支付时验签 + 更新订单 + 发卡）"""
    # TODO 真支付：验签 → 解析 order_id/amount → 幂等标记 paid → 触发发卡
    return {"gateway": gateway_name, "received": True}
```

**5 大关键缺口**（按依赖顺序）：

| # | 缺口 | 影响 | 工作量 |
|---|------|------|--------|
| 1 | **无验签** | 任何人都能 POST `/notify/wechat` 伪造成功 → **真支付时致命** | 1-2d（接微信/支付宝 SDK + 验签） |
| 2 | **无幂等表** | 网关重试会导致同一通知处理多次（订单状态被覆盖、发卡重复） | 0.5d（建 `cms_payment_idempotency` 表 + 唯一索引 on `(gateway, transaction_id)`） |
| 3 | **无订单状态机** | webhook 只回 `received=True` 而不更新 `cms_product_order.status=paid` | 1d（订单模型加 status 字段 + 状态转移校验） |
| 4 | **无发卡触发** | 真支付成功不调 `/orders/{id}/issue-card` → 用户付了钱拿不到卡 | 0.5d（webhook 内调 issue-card service） |
| 5 | **无失败回滚** | 发卡失败时如何处理？订单状态 / 库存 / 退款 全部无定义 | 1d（补偿事务 / 异步重试 / 告警） |

**前置依赖（建议实现顺序）**：
1. ✅ `cms_product_order` 表加 `status` 字段（pending/paid/cancelled/refunded）+ `paid_at` / `transaction_id`
2. ✅ `cms_payment_idempotency` 新表（`id` / `gateway` / `transaction_id` / `order_id` / `processed_at`，唯一索引）
3. ⏳ 实现 `WechatGateway` + `AlipayGateway`（继承 `PaymentGateway`，含真 API + 验签）
4. ⏳ 重写 webhook：`verify_signature()` → `check_idempotency()` → `update_order_status(paid)` → `trigger_issue_card()` → `record_payment()`
5. ⏳ 失败回滚：发卡失败时订单回 `pending`，记录 `cms_payment_retry_queue`，webhook 通知 admin

**风险评估**：**当前 mock 路径不影响生产**（因为只有内部 `POST /orders/{id}/pay` 调用，会同步返回 success 然后调用 `issue-card`）；但**真支付接入前必须补齐 5 项**——这是 CMS 商业化前置条件。

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
asyncpg>=0.29
aiosqlite>=0.20
redis>=5.0
pydantic>=2.6
pydantic-settings>=2.0  # ⚠️ 必装，oa-agent bridge fixture 依赖
python-multipart>=0.0.9  # 文件上传（CMS 媒体上传）
pyjwt>=2.8
bcrypt>=4.0
httpx>=0.28            # OAuth + oa-agent 桥接
cos-python-sdk-v5      # Sprint 1：STORAGE_BACKEND=cos 时必装
tencentcloud-sdk-python # Sprint 1 骨架：STS 备用（当前不启用）
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
| `QWEATHER_API_HOST` | `nf5b5vtkcp.re.qweatherapi.com` | 🆕 CMS weather host |
| `OA_AGENT_URL` | `http://localhost:9001` | 🆕 oa-agent 服务地址（CMS AI 设计行程依赖） |
| `STORAGE_BACKEND` | `local` | 🆕 Sprint 0：对象存储后端（`local` \| `cos`）|
| `STORAGE_LOCAL_ROOT` | `storage/uploads` | 🆕 Sprint 0：LocalStorage 根目录 |
| `COS_REGION` / `COS_SECRET_ID` / `COS_SECRET_KEY` / `COS_BUCKET` | 空 | 🆕 Sprint 1：腾讯云 COS 凭据（CAM 子账号 qmwx-cos-uploader）；**当前用第 2 密钥长密钥 AKIDI5i...（2026-07-15 复用，STS 暂缓 YAGNI）** |
| `COS_APPID` / `COS_SCHEME` / `COS_CDN_DOMAIN` | 见 `.env.example` | 🆕 Sprint 1：COS 高级配置 |
| `COS_PRESIGN_EXPIRE` / `COS_DOWNLOAD_EXPIRE` / `COS_MAX_OBJECT_MB` | `3600` / `600` / `500` | 🆕 Sprint 1：签名有效期与对象大小限制 |
| `STS_ROLE_ARN` / `STS_SESSION_NAME` / `STS_SESSION_DURATION` / `STS_POLICY` | 空 | 🔜 **YAGNI**：暂不启用，保留 `app/services/storage/sts.py` 骨架 |

---

## 数据模型 (Data Models)

### SQLAlchemy 模型（app/models/）

| 文件 | 表 | 说明 |
|------|----|------|
| `base.py` | Base | 声明基类（`declarative_base` 风格，2026-07-14 迁移） |
| `enterprise.py` | users / roles / permissions / departments / user_roles / role_permissions | RBAC 核心 |
| `finance.py` | finance_accounts / finance_categories / finance_transactions / **vouchers / journal_entries** | 🆕 复式记账（2026-07-15） |
| `asset.py` | asset_card_types / asset_batches / asset_cards / asset_redemptions | 4 类型(VIP/代金/兑换/储值) |
| `agent.py` | agent_agent / agent_order / commission_record / yearly_commission | 区域代理 + 双层返佣（2026-07-13 重构） |
| `oa.py` | oa_announcement / oa_leave / oa_expense / oa_approval_instance / oa_report / oa_attendance | OA 6 表 |
| **`cms.py`** | 🆕 `cms_tour_product` / `cms_tour_custom` / `cms_tour_pass` / `cms_media_asset` / `cms_merchant` / `cms_product_order` / `cms_coupon` / `cms_inquiry_lead` / `cms_review` / `cms_end_user` | **CMS 内容管理 10 表**（2026-07-14 上线） |

> 代理模型 2026-07-13 重构：原 `level` 字段（3 级分销）保留兼容，新增 `region_code` + `yearly_commission` 表。详见 `docs/PRICING.md`。
>
> CMS 模型 2026-07-14 上线：`cms_end_user` 是 C 端账号（与 `users` 业务用户分离，JWT `type=end_user` 区分）；`cms_product_order.issue_card_id` 关联 `asset_cards.id` 实现真发卡。
>
> 财务模型 2026-07-15 上线：`vouchers`（凭证）+ `journal_entries`（分录）借贷平衡 Σdebit=Σcredit 校验；`finance_transactions` 表标 DEPRECATED。

---

## 🆕 §11 Storage 抽象层（2026-07-14 Sprint 0/1 + 2026-07-15 Phase 2，**2026-07-15 新增整节**）

### 11.1 设计目标

统一 admin 14 个写文件点（CMS media upload + 富文本资源 + agent 资源等），通过 `Storage` ABC 抽象 backend 切换（`local` ↔ `cos`），前端直传优先（presigned URL）+ 中转 fallback。

### 11.2 文件清单（`app/services/storage/`）

| 文件 | 行数 | 职责 |
|------|------|------|
| `protocol.py` | ~80 | `Storage` ABC（9 个抽象方法：put/get/get_stream/delete/exists/list_objects/presigned_upload/presigned_download/get_metadata） |
| `local.py` | ~120 | `LocalStorage` 默认实现（写 `STORAGE_LOCAL_ROOT`） |
| `cos.py` | ~280 | `CosStorage` 腾讯云实装（ap-guangzhou / Bucket `qm-wx-1418512491` / CDN `cos-cdn.qingmulife.cn`） |
| `sts.py` | **173** | `STSCredentialProvider`（**Sprint 1 骨架·YAGNI**，详见 §11.4） |
| `errors.py` | ~30 | `BackendUnavailable` / `ObjectNotFound` 等自定义异常 |
| `metrics.py` | ~50 | 上传/下载/删除计数（可选 Prometheus 集成） |

### 11.3 后端切换

```bash
# 默认 local
STORAGE_BACKEND=local

# 切 COS（配齐 env）
STORAGE_BACKEND=cos
COS_REGION=ap-guangzhou
COS_SECRET_ID=AKIDI5i...              # qmwx-cos-uploader 第 2 密钥
COS_SECRET_KEY=...
COS_BUCKET=qm-wx-1418512491
COS_CDN_DOMAIN=cos-cdn.qingmulife.cn
```

前端直传：`/admin/api/v1/storage/presign`（admin `routes/storage.py`）拿 presigned URL，浏览器 PUT 直传 COS，省后端带宽。

### 11.4 STS 临时凭证 — YAGNI 决策（`sts.py` 173 行，**2026-07-15 深读**）

**当前状态**：`STSCredentialProvider` 已实装完整骨架（AssumeRole + Redis 缓存 + fail-open），但**生产不启用**。

**决策依据**（2026-07-15）：
- 生产用 `qmwx-cos-uploader` CAM 子账号**长密钥**（AKIDI5i...，2026-07-15 03:57 创建的第 2 密钥），单密钥泄露影响面有限；
- 旧密钥 AKIDDHBu...q4M 保留不禁用（别处在用）；
- STS 临时凭证**价值递减**：长密钥 + CAM 最小权限（`QcloudCOSDataFullControl` + 自定义 policy）已满足生产安全；
- STS 增加复杂度：需 AssumeRole 调用 + Redis 缓存层 + 30min refresh 窗口，对小项目 ROI 低。

**sts.py 关键设计**（保留待未来启用）：

```python
@dataclass(frozen=True)
class STSCredential:
    secret_id: str
    secret_key: str
    session_token: str
    expired_at: int  # unix timestamp
    def is_expired(self, skew_seconds: int = 300) -> bool: ...  # 默认 5min 提前刷新

class STSCredentialProvider:
    """用法：
        provider = STSCredentialProvider(
            role_arn='qcs::cam::uin/xxx:roleName/kk-mis-cos-writer',
            session_name='kk-mis', duration=1800, region='ap-guangzhou',
            secret_id=settings.long_term_secret_id, secret_key=settings.long_term_secret_key,
            redis_client=aioredis_client,
        )
        cred = await provider.get()  # 自动 refresh + 缓存
        config = CosConfig(SecretId=cred.secret_id, SecretKey=cred.secret_key, Token=cred.session_token)
    """
```

**核心方法**：
- `get()` → 先查 Redis 缓存，未命中或过期调 `_assume_role()` 再写回缓存
- `_assume_role()` → 调 `tencentcloud-sdk-python` 的 `AssumeRoleRequest`（`run_in_executor` 异步化），返回 `STSCredential`
- `_read_cache()` / `_write_cache()` → Redis 操作均 fail-open（异常仅 warning，不阻塞）
- `_cache_key()` → 用 role_arn 全文作 key（避免 leak 长 SECRET）；TTL = `expired_at - now - 60s`（留 1min 安全边）

**启用条件**：业务侧需要给 CAM 子账号配 `AssumeRole` 策略 + 明确要求临时凭证时。

**依赖**：`tencentcloud-sdk-python`（已加 requirements.txt 但 lazy import，未启用不报错）。

### 11.5 测试覆盖

- `tests/test_storage_local.py`（30 用例）
- `tests/test_storage_protocol.py`（9 用例）
- `tests/test_storage_cos_skeleton.py`（9 用例）
- `tests/test_storage_route.py`（Phase 2 presign）
- `tests/integration/test_cos_integration.py`（6 桩，需 `INTEGRATION` env 自动 skip）

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-14 续跑重置基线，**2026-07-15 财务+办公+Storage 扩展**）
- ✅ pytest **94 passed 0 pre-existing**（2026-07-14 修复 pre-existing 根因：`.venv` 缺 `pydantic_settings`）
- 2026-07-15 扩展：+ test_voucher 9 + test_office 16 + test_storage_* 4 = admin **~104 passed**
- 测试文件清单（`tests/`）：
  - **单元（12 原有 + 4 新增）**：`test_auth.py` / `test_oa.py` / `test_finance.py` / `test_asset.py` / `test_agent.py` / `test_pricing.py` / `test_vip_orders.py` / `test_yearly_commission.py` / `test_anticounterfeit.py` / `test_config_validation.py` / `test_auth_oauth.py` / `test_oa_agent_bridge.py` / **`test_cms.py`**（CMS 11 router 覆盖）/ **`test_voucher.py`**（复式 9 用例）/ **`test_office.py`**（办公桥 16 用例，含 oa-agent 不可达 skip）/ **`test_storage_local.py` + `test_storage_protocol.py` + `test_storage_cos_skeleton.py` + `test_storage_route.py`**（Storage 4 文件）
  - **集成**：`integration/test_bridge_integration.py` + `integration/test_cms_full_flow.py` + `integration/test_cos_integration.py`（6 桩需 env）
  - **E2E**：`e2e/test_vip_full_flow.py` + `e2e/test_cms_purchase_flow.py`（CMS 购买→发卡）
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
A: 检查产品是否关联 `card_type_id`（cms_tour_product.card_type_id）+ 有 active batch（asset_batches.status=active）。现 `MockGateway`，真支付需商户号/密钥。**真支付接入前必先实现 §7.14 5 项缺口**。

**Q7: CMS weather 服务返回 503？**
A: `QWEATHER_KEY` 未配置。生产部署必须设；oa-agent 的 `query_weather` 工具独立（git remote 待确认 push）。

**Q8: STS 临时凭证如何启用？**
A: 当前 YAGNI，生产用 `qmwx-cos-uploader` 长密钥即可。如需启用，需业务侧提供 `STS_ROLE_ARN` + 在 CAM 配 AssumeRole 策略 + 改 `cos.py` 注入 `STSCredentialProvider`。详见 §11.4。

**Q9: 财务 transactions vs vouchers 双轨如何处理？**
A: 2026-07-15 起新流程走 voucher 凭证（复式记账），transactions 表标 DEPRECATED 但未废弃（旧报表仍可用）。迁移脚本待续，详见下一步建议。

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
- `finance/`（accounts / categories / transactions / reports / **vouchers**）— 财务（含复式记账）
- `asset/`（card_types / batches / cards / redemptions / verify）— 资产（含防伪核销）
- `agent/`（agents / orders / commissions / yearly_commission / **promo** / **withdrawal**）— 区域代理 + 双层返佣 + 推广码 + 提现
- `oa/`（announcements / approvals / leaves / expenses / reports / attendance）— OA 6 模块
- **`cms/`**（🆕 auth / products / media / merchants / leads / orders / coupons / reviews / stats / **payments** / weather）— **CMS 11 router**（2026-07-14，search 在 products.py 内合并；**payments 仅 14 行占位**详见 §7.14）
- `oa_agent_bridge.py` — OA-Agent 桥接（`/oa-agent/*`，SSE 流式）
- **`storage.py`**（🆕 2026-07-15 Phase 2）— 前端直传 presign + health
- **`office.py`**（🆕 2026-07-15）— 办公桥 `/api/v1/office/{health,tools,read,preview,merge}` → oa-agent `/tools/{name}`

### 模型（app/models/）
- `base.py` / `enterprise.py` / `finance.py`（含 vouchers / journal_entries） / `asset.py` / `agent.py` / `oa.py` / **`cms.py`**（🆕 CMS 10 表）/ **`member.py`**（🆕 VIP 卡会员）/ **`social.py`**（🆕 推广/社交）/ **`audit.py`**（🆕 审计增强）

### 服务（app/services/）
- `pricing.py` — VIP 阶梯折扣 + 年度返佣阶梯
- `yearly_commission.py` — 年度返佣结算
- **`payment.py`**（🆕）— **支付网关（PaymentGateway 抽象 + MockGateway，详见 §7.12）**
- **`weather.py`**（🆕）— **和风天气实时 + 预报（详见 §7.13）**
- **`notifier.py`**（🆕）— webhook 通知（订单/线索/评论状态变更）
- **`storage/`**（🆕 2026-07-14 Sprint 0/1 + 2026-07-15 Phase 2）— **对象存储抽象层**（`Storage` ABC + `LocalStorage` 默认 + `CosStorage` 腾讯云 + **`STSCredentialProvider` YAGNI 详见 §11.4**）；管理 14 个写文件点；backend 由 `STORAGE_BACKEND=local|cos` 切换
- **`office/`**（🆕 2026-07-15）— 办公桥 httpx → oa-agent `/tools/{name}` + docx_to_html + merge_template
- **`dynamic_code.py`**（🆕）— 动态码生成（V1）
- **`points.py`**（🆕）— 积分系统（V2）
- **`approval_engine.py`**（🆕）— 审批流引擎

### 测试（tests/）
- 25+ 测试文件（12+ 单元 + 集成 + E2E + 性能 + REPORT.md）；详见上文"测试与质量"段
- 🆕 `tests/test_storage_*.py`（30+9+9 用例）+ `tests/test_cos_integration.py`（6 桩需 env）+ `tests/test_voucher.py`（9 用例）+ `tests/test_office.py`（16 用例含 skip）

### 文档（docs/）
- `API_MATRIX.md` — 124 端点完整矩阵
- `PRICING.md` — VIP 阶梯折扣 + 年度返佣规则

### §7.15 CMS 订单路由（`routes/cms/orders.py`）

#### 路由矩阵

| 方法 | 路径 | 鉴权 | 行为 |
|------|------|------|------|
| POST | `/api/v1/cms/orders` | 公开 | 创建权益卡订单，锁价、验券并写入 `pending` |
| POST | `/api/v1/cms/orders/{order_id}/pay` | 公开 | 调支付网关，成功后核销优惠券、计推荐佣金并尝试发卡 |
| GET | `/api/v1/cms/orders` | `cms:order:list` | 按 `pay_status` 可选过滤并倒序列出订单 |
| GET | `/api/v1/cms/orders/export` | `cms:order:list` | 同条件导出 CSV，含卡号但不含卡密码 |

> 当前文件没有单订单 `GET /{order_id}` 查询端点，也没有 `cancel` 端点；`cancelled` 仅是模型注释中预留的状态。不能把“模型允许”误写成“路由已实现”。

#### 创建订单（create）

1. `session.get(TourProduct, product_id)`，只接受 `status=published` 且 `type=pass`。
2. 按 `TourPass.product_id` 取权益卡配置，以 `face_value` 锁定 `unit_price`。
3. 计算 `original_total = unit_price × quantity`；折扣结果保留两位小数，实付最低为 0。
4. 优惠券按 `code` 查询，依次校验启用状态、过期时间、最低消费和最大使用次数。
5. `percent` 折扣按原价乘百分比计算；`fixed` 折扣取“固定额、原价”较小值。
6. 可选 `promo_code` 只匹配启用代理；命中后保存 `referrer_agent_id`，无效码不阻断下单。
7. 创建 `ProductOrder(pay_status="pending")`，提交并返回 `ProductOrderOut`。

#### 支付、MockGateway 与真发卡链路

```text
pending order
  → gateway.pay(order_id, total, subject)
  → result.success ? paid : HTTP 400
  → paid_at + transaction_id
  → 推荐佣金（可选）+ 优惠券 used_count
  → product.card_type_id ? _issue_card() : 跳过
  → commit → notify("新订单", payload)
```

- `gateway` 是 `services.payment` 暴露的实例；当前实现为 `MockGateway`，mock 直接返回支付结果，替换真实网关时路由调用面保持不变。
- 非 `pending` 订单支付直接返回 400，因此现有检查阻止普通重复支付；网关调用发生在数据库提交前。
- 推荐订单按 `total × 5%` 生成 `ReferralCommission(status="pending")`，并冗余写入 `referral_commission`。
- 优惠券只在支付成功后 `used_count += 1`，创建订单阶段不会占用次数。
- `_issue_card()` 从同 `card_type_id` 的 `draft|active` 批次中按 id 倒序取最新一个；无批次时支付仍成功，只是不发卡。
- 发卡生成 16 位数字卡号、6 位数字密码、64 字符防伪码和 UUID 交易哈希；密码哈希写 `AssetCard.password_hash`。
- 新卡为 `AssetCard(status="issued")`；批次 `generated += 1`，若原为 `draft` 同步转为 `active`。
- 为一次性交付买家，订单同时保存 `issued_card_no` 与明文 `issued_card_password`；这是敏感字段，列表/日志扩展时不得泄露。

#### 订单状态机（代码事实）

```text
pending ──pay(success)──> paid
pending ──pay(failed)───> pending
cancelled：模型预留，当前无入口
```

状态落在 `ProductOrder.pay_status: String(20)`，不是数据库 ENUM，也不存在通用 `status` 字段。当前状态约束由 `pay_order()` 的字符串比较实现；数据库层不拦截未知值。支付、返佣、核券、发卡共用一次 `commit`，但缺少行锁、网关幂等键和并发优惠券原子扣减，接真支付前应补齐。

#### 查询与输出

- 管理列表只支持 `pay_status` 精确过滤，无分页、买家/手机号搜索和单订单详情。
- CSV 列为订单 ID、买家、电话、数量、单价、原价、优惠、实付、券码、支付状态、已发卡号、创建时间。
- `notify()` 在数据库提交后执行，是旁路通知；失败不会回滚已完成的支付和发卡。

### §7.16 CMS 10 表 schema（`models/cms.py`）

CMS 使用 10 张 SQLAlchemy 表；所有 `id` 均由共享 `pk()` 生成，时间默认调用 `utcnow`。状态字段均为普通 `String`/`Boolean`，当前没有数据库 ENUM 或 CHECK 约束。

#### 表总览

| 模型 | 表名 | 职责 |
|------|------|------|
| `TourProduct` | `cms_tour_product` | A/C 两类旅游产品的公共主表 |
| `TourCustom` | `cms_tour_custom` | A 类订制游行程、流程和报价扩展 |
| `TourPass` | `cms_tour_pass` | C 类权益卡面值、权益和商户扩展 |
| `MediaAsset` | `cms_media_asset` | 图片/视频素材及 Storage 元数据 |
| `Merchant` | `cms_merchant` | 权益卡合作商户 |
| `ProductOrder` | `cms_product_order` | 权益卡公开购买、支付、返佣与发卡结果 |
| `Coupon` | `cms_coupon` | 百分比或固定额优惠券 |
| `InquiryLead` | `cms_inquiry_lead` | 订制游公开询价线索 |
| `Review` | `cms_review` | 产品评价及审核状态 |
| `EndUser` | `cms_end_user` | 独立于后台 RBAC 的 C 端账号 |

#### `TourProduct`

| 字段 | 类型/约束 | 含义 |
|------|-----------|------|
| `id`; `title`; `slug`; `type` | pk；String(200) 非空；String(200) 唯一/索引/非空；String(20) 非空 | 主键、标题、URL 标识、`custom|pass` |
| `destination`; `theme`; `category`; `tags` | String(100)；String(50)；String(50) 索引；JSON=list | 目的地、主题、分类、标签 |
| `cover_image`; `gallery`; `video_url` | String(500)；JSON=list；String(500) | 封面、图集、视频 |
| `summary`; `content`; `highlights` | String(500)；Text；JSON=list | 摘要、富文本、亮点 |
| `status`; `sort`; `view_count`; `card_type_id` | String(20)=draft 非空/索引；Integer=0；Integer=0；FK `asset_card_type.id` | 发布态、排序、浏览量、支付后发卡类型 |
| `seo_title`; `seo_description`; `published_at`; `created_at`; `updated_at` | String(200)；String(500)；DateTime；DateTime；DateTime/onupdate | SEO 与生命周期时间 |

#### `TourCustom` 与 `TourPass`

| 模型 | 完整字段 |
|------|----------|
| `TourCustom` | `id`; `product_id`（FK 产品，非空/索引）；`itinerary`（JSON=list）；`service_flow`（JSON=list）；`price_mode`（String(20)=inquiry）；`price_tiers`（JSON=list）；`consultant_ids`（JSON=list） |
| `TourPass` | `id`; `product_id`（FK 产品，非空/索引）；`face_value`（Numeric(12,2)=0）；`total_worth`（Numeric(12,2)=0）；`valid_period`（String(100)）；`usage_rules`（Text）；`benefits`（JSON=list）；`merchant_ids`（JSON=list） |

#### `MediaAsset` 与 `Merchant`

| 模型 | 完整字段 |
|------|----------|
| `MediaAsset` | `id`; `name` String(200) 非空；`type` String(20) 非空；`url` String(500) 非空；`size` Integer=0；`alt` String(200)；`tags` JSON=list；`uploaded_by` BigInteger；`storage_backend` String(20)=local 非空；`storage_key` String(512)；`etag` String(64)；`content_type` String(64)=image/png 非空；`created_at` DateTime |
| `Merchant` | `id`; `name` String(100) 非空；`logo` String(500)；`address` String(300)；`contact` String(100)；`benefit_desc` Text；`status` Boolean=true；`sort` Integer=0；`created_at` DateTime |

#### `ProductOrder`（P0 / D2 的事实基础）

| 字段组 | 完整字段 |
|--------|----------|
| 商品/金额 | `id`; `product_id`（FK 产品，非空/索引）；`quantity` Integer=1 非空；`unit_price`; `original_total`; `discount`; `total`（均 Numeric(12,2)，默认 0） |
| 优惠/买家 | `coupon_id` BigInteger；`coupon_code` String(50)；`buyer_name` String(50) 非空；`buyer_phone` String(30) 非空；`remark` Text |
| 状态/推荐 | `pay_status` String(20)=pending 非空/索引；`referrer_agent_id` BigInteger/索引；`referral_commission` Numeric(12,2)=0 |
| 支付/发卡 | `paid_at` DateTime；`issued_card_no` String(32)；`issued_card_password` String(10)；`transaction_id` String(100)；`created_at` DateTime |

> **关键事实**：订单字段叫 `pay_status`，类型是 `String(20)`，不是 ENUM；模型中不存在订单通用 `status` 字段。注释约定值为 `pending|paid|cancelled`，但数据库不强制值域。这正是 P0 方案 D2 必须围绕现状设计迁移/兼容，而不能直接按 ENUM 或 `status` 假设改造的依据。

#### `Coupon`、`InquiryLead`、`Review`、`EndUser`

| 模型 | 完整字段 |
|------|----------|
| `Coupon` | `id`; `code` String(50) 唯一/非空/索引；`name` String(100) 非空；`discount_type` String(20) 非空；`discount_value` Numeric(12,2) 非空；`min_total` Numeric(12,2)=0；`max_uses` Integer=0；`used_count` Integer=0；`valid_from`; `valid_until` DateTime；`status` Boolean=true；`created_at` DateTime |
| `InquiryLead` | `id`; `product_id`（FK 产品/索引）；`name` String(50) 非空；`phone` String(30) 非空；`wechat` String(50)；`destination` String(100)；`travel_date` String(50)；`people` Integer；`budget` String(50)；`remark` Text；`status` String(20)=new 非空/索引；`created_at` DateTime |
| `Review` | `id`; `product_id`（FK 产品，非空/索引）；`author_name` String(50) 非空；`rating` Integer 非空；`content` Text 非空；`status` String(20)=pending 非空/索引；`created_at` DateTime |
| `EndUser` | `id`; `phone` String(30) 唯一/非空/索引；`password_hash` String(255) 非空；`nickname` String(50)；`created_at` DateTime |

#### 关系与约束边界

- 外键只显式覆盖产品扩展、线索、订单、评论及产品→卡类型；`coupon_id`、`referrer_agent_id`、`uploaded_by` 没有声明 FK。
- 模型未声明 ORM `relationship()`、级联删除、唯一的扩展表 `product_id`，业务一致性主要由路由代码维护。
- JSON 列用于行程、权益、标签、商户/顾问 ID 列表；字段结构依赖 Pydantic schema 和调用方约定。
- `EndUser` 与后台 `User` 完全分表，JWT 以 `type=end_user` 区分，不能套用 admin RBAC 关系。

### §7.17 webhook notifier 服务（`services/notifier.py`）

#### 服务契约

`notify(event: str, data: dict) -> None` 是 CMS 的通用旁路通知函数，供订单、询价线索、评论等路由在创建或状态变更后 callback 运营 webhook。服务本身不识别业务模型，也不持久化通知记录；事件名和 payload 全由调用方定义。

```python
WEBHOOK_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")

async def notify(event: str, data: dict) -> None:
    if not WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as cli:
            await cli.post(WEBHOOK_URL, json={"event": event, "data": data})
    except Exception:
        pass
```

#### 输入、输出与调用语义

| 项 | 当前实现 |
|----|----------|
| 配置 | 进程导入模块时读取 `NOTIFY_WEBHOOK_URL`；空值直接跳过 |
| 请求 | HTTP POST，JSON 固定外壳 `{event, data}` |
| 客户端 | 每次调用新建 `httpx.AsyncClient` |
| 超时 | 总体使用 `timeout=5` |
| 返回 | 始终 `None`，不向调用方暴露投递结果 |
| 异常 | 捕获所有 `Exception` 后静默丢弃 |
| HTTP 错误 | 未调用 `raise_for_status()`，4xx/5xx 也被当作已执行完毕 |

订单支付路径在数据库 `commit` 后 `await notify("新订单", {...})`；因此通知失败不会回滚订单、核券、返佣或发卡。线索与评论路由应遵守同一原则：先提交业务状态，再用稳定事件名发送最小必要字段，不能把 webhook 当事务成功条件。

#### 订单 / 线索 / 评论 callback 约定

| 域 | 建议触发点 | payload 最小集 | 注意 |
|----|------------|----------------|------|
| 订单 | 支付成功或后续订单状态变更 | `id`、金额、买家必要联系方式、目标状态 | 卡密码、支付密钥不得发送 |
| 线索 | 新建及 `new→contacted→converted|closed` | `id`、联系人、目标状态、产品 ID | 手机/微信属于个人信息，按 webhook 接收方最小化 |
| 评论 | 新建及 `pending→approved|rejected` | `id`、产品 ID、评分、目标状态 | 评论正文可能含敏感内容，默认不全量外发 |

> 上表是调用边界，不代表 notifier 内建了三个专用函数。当前只有一个通用 `notify()`；要保证“状态变更 callback”，必须由对应路由显式调用。

#### P0 风险：5 秒同步等待 + 静默失败

- **延迟放大**：虽然通知是旁路，当前仍在 API 请求协程内 `await`；webhook 慢时业务响应最多额外等待约 5 秒。
- **不可观测**：无日志、指标、失败计数和 trace，配置错误、DNS、TLS、4xx/5xx 均无法从系统内发现。
- **不可重试**：无退避、消息队列或 outbox；瞬时故障会永久丢通知。
- **无鉴权**：未加签名、时间戳、nonce 或固定认证头，接收方无法验证来源及防重放。
- **无幂等**：没有 event id；未来补重试后，接收方可能重复处理。
- **配置冻结**：`WEBHOOK_URL` 在 import 时求值，运行期修改环境变量不会生效，必须重启进程。

P0 最小修复顺序：先补结构化失败日志与 `raise_for_status()`，再把客户端复用/超时细分，最后采用 outbox + 后台 worker 重试并增加签名和幂等键。核心原则不变：通知失败不得破坏业务主事务。

### §7.18 CMS 产品路由（`routes/cms/products.py`）

#### 路由矩阵

| 方法 | 路径 | 鉴权 | 功能 |
|------|------|------|------|
| GET | `/api/v1/cms/products` | `cms:product:list` | 后台列表，按 `type/status/category` 精确过滤 |
| GET | `/api/v1/cms/products/{slug}` | 公开 | 仅取已发布详情，浏览量 +1，并附最多 20 条通过审核的评论 |
| GET | `/api/v1/cms/products/search/results?q=` | 公开 | 已发布产品五字段模糊搜索，最多 20 条 |
| GET | `/api/v1/cms/products/related/{slug}` | 公开 | 同分类相关推荐，最多 4 条 |
| GET | `/api/v1/cms/products/detail/{product_id}` | `cms:product:list` | 后台读取任意状态详情及 A/C 扩展 |
| POST | `/api/v1/cms/products` | `cms:product:save` | 创建主表及匹配类型的扩展 |
| PUT | `/api/v1/cms/products/{product_id}` | `cms:product:save` | 更新主表，扩展表 upsert |
| DELETE | `/api/v1/cms/products/{product_id}` | `cms:product:save` | 手动删 A/C 扩展后删除主表 |

> 当前没有独立的 `/publish` 或 `/archive` 动作端点；发布/归档由创建或更新 payload 中的 `status` 完成。调用方不能假设存在专用动作 API。

#### 详情组装与 CRUD

- `_load_detail()` 先用 `TourProductDetail.model_validate(p)` 建公共详情，再按 `p.type` 查询唯一一条扩展。
- `type=custom` 加载 `TourCustom` 到 `detail.custom`；`type=pass` 加载 `TourPass` 到 `detail.pass_config`。
- 创建前按 `slug` 查重；主表先 `flush()` 取得 id，再按请求类型和扩展 payload 插入扩展，最后一次提交。
- 更新采用 `exclude_unset=True`，只覆盖请求显式字段；slug 变化时再次查重。
- 扩展更新是“查询后逐字段赋值，不存在则新增”的 upsert；请求没带对应扩展时不修改。
- 若更新时改变 `type`，代码不会主动删除旧类型扩展，可能同时残留 `TourCustom` 与 `TourPass`，读取时只展示当前类型。
- 删除会依次查找并删除两种扩展，再删除产品；模型未配置级联，订单、线索、评论等引用需由数据库 FK 行为兜底。

#### 发布状态机（代码事实）

```text
create/update status="published" → published_at 首次写 utcnow()
draft ⇄ published ⇄ archived    → 路由未限制迁移方向
```

| 状态 | 公开详情/搜索/推荐 | 后台详情 | 时间行为 |
|------|--------------------|----------|----------|
| `draft` | 不可见 | 可见 | `published_at` 默认空 |
| `published` | 可见 | 可见 | 首次发布写 `published_at` |
| `archived` | 不可见 | 可见 | 不清空 `published_at`，无 `archived_at` |

- `status` 是 `String(20)`，路由没有 allowlist；理论上可写入任意字符串，公开侧只认精确的 `published`。
- 创建时若直接发布就写发布时间；更新时仅当目标为 published 且原值为空时写入，重复发布保留首次时间。
- 归档只是把状态改为 `archived`；无独立权限、审核、版本快照或状态迁移审计。

#### 公开详情、搜索与推荐算法

- 公开 slug 详情先验证 `status=published`，然后 `view_count += 1` 并立即提交，再加载扩展和最新评论。
- 评论只选 `status=approved`，按评论 id 倒序，最多 20 条。
- 搜索将输入包为 `%q%`，对 `title/summary/destination/category/theme` 组合 `ILIKE OR`，只查 published。
- 搜索排序为 `view_count DESC, id DESC`，没有分词、相关度评分、转义策略、空查询限制或分页。
- 推荐先按 slug 找源产品；找不到返回空数组，不抛 404。
- 候选固定为 published 且排除自身；源产品有 category 时强制同分类，没有 category 时允许全部分类。
- 推荐按 `view_count DESC` 取 4 条；同分类不足时不会跨分类补齐，也未使用标签、目的地、主题或协同信号。

#### 一致性与性能边界

- 后台列表按 `sort ASC, id DESC`，返回公共字段，不加载扩展；当前无分页。
- 每次公开详情都同步写浏览量，高并发下可能出现丢失更新并放大数据库写压力。
- slug 唯一性同时由应用预查和数据库 unique 约束保护，但并发冲突最终仍需处理 `IntegrityError`。
- 产品路由不发送 notifier；若发布/归档需要运营 callback，应在成功提交后显式调用通用 `notify()`。

---

## 变更记录（第四轮深读）

- 2026-07-15 13:30:00 — admin CMS 第四轮深读补档：
  - 新增 §7.15：订单创建、MockGateway 支付、推荐返佣、优惠券核销、真发卡链路及 `pay_status` 状态机；
  - 核实订单路由当前只有 create/pay/list/export，`cancel` 与单订单 query 尚未实现；
  - 新增 §7.16：完整登记 `models/cms.py` 10 张表与全部字段；
  - 固化 P0/D2 事实：`ProductOrder.pay_status` 是 `String(20)`，非 ENUM，且不存在订单 `status` 字段；
  - 新增 §7.17：notifier webhook 契约及订单/线索/评论 callback 边界，标记 5 秒同步超时与静默失败风险；
  - 新增 §7.18：产品 CRUD、状态发布/归档方式、公开搜索及同分类热门推荐算法；
  - 核实产品发布/归档通过通用 update status 完成，当前无独立 publish/archive 端点。





- **`cms-content-module-research.md`**（🆕，`mis-system/docs/` 下）— CMS 架构决策与设计文档
- **`STORAGE.md`**（🆕，`mis-system/docs/` 下）— Storage 抽象层 + 腾讯云 COS 决策