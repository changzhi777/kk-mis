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

---

### §7.19 P0 Day 1.1 alembic migration 详解（`alembic/versions/20260715_cms_payment_webhook_p0.py` · 草案）

> ⚠️ **当前状态**：admin 服务**尚未启用 alembic**（仓库内无 `alembic/` 目录）。本节是 P0 Day 1.1 实施产物的**设计草案**，落到代码时需先 `alembic init alembic` + 配 `env.py` 指向 `Base.metadata`，再落本文件。下方 SQL 是兼容 SQLite（开发）与 PostgreSQL（生产）的版本；ENUM 在 SQLite 退化为 `VARCHAR + CHECK`。

#### 迁移文件骨架

```python
# mis-system/services/admin/alembic/versions/20260715_cms_payment_webhook_p0.py
"""P0 CMS 支付 webhook 与多卡履约迁移

Revision ID: 20260715_cms_payment_webhook_p0
Revises: <head>  # 由 alembic 当时实际 head 替换
Create Date: 2026-07-15 14:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260715_cms_payment_webhook_p0"
down_revision = None  # 实跑前查 alembic_version 表填入真 head
branch_labels = ("cms-p0",)
depends_on = None


def upgrade() -> None:
    # 1) ProductOrder 状态机迁移：order_no / status / provider
    op.add_column("cms_product_order", sa.Column("order_no", sa.String(40), nullable=True))
    op.add_column("cms_product_order", sa.Column("status", sa.String(20), nullable=True))
    op.add_column("cms_product_order", sa.Column("provider", sa.String(20), nullable=True))
    op.add_column("cms_product_order", sa.Column("paid_at", sa.DateTime(), nullable=True))
    op.create_index("ix_cms_order_order_no", "cms_product_order", ["order_no"], unique=True)
    # 历史数据回填：旧 id 转 order_no（旧字段 pay_status → status 映射见 P0 §3.3.3）
    op.execute("UPDATE cms_product_order SET order_no = 'LEGACY-' || id WHERE order_no IS NULL")
    op.execute("""
        UPDATE cms_product_order SET status =
          CASE pay_status
            WHEN 'pending' THEN 'pending'
            WHEN 'cancelled' THEN 'cancelled'
            WHEN 'paid' THEN CASE WHEN issued_card_no IS NOT NULL THEN 'fulfilled' ELSE 'paid' END
            ELSE 'pending'
          END
        WHERE status IS NULL
    """)
    op.alter_column("cms_product_order", "order_no", nullable=False)
    op.alter_column("cms_product_order", "status", nullable=False)
    # 复合唯一：(provider, transaction_id) 仅在 transaction_id 非空时生效
    op.create_index(
        "uq_cms_order_provider_txn", "cms_product_order",
        ["provider", "transaction_id"], unique=True,
        postgresql_where=sa.text("transaction_id IS NOT NULL"),
    )

    # 2) cms_payment_idempotency（事件幂等闸门）
    op.create_table(
        "cms_payment_idempotency",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_id", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.String(100), nullable=False),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("cms_product_order.id"), nullable=True),
        sa.Column("amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(8), server_default="CNY", nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="processing", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider", "event_id", name="uq_cms_pay_event"),
        sa.UniqueConstraint("provider", "transaction_id", name="uq_cms_pay_transaction"),
    )
    op.create_index("ix_cms_pay_order", "cms_payment_idempotency", ["order_id"])

    # 3) cms_payment_retry_queue（持久化发卡任务 + 租约恢复）
    op.create_table(
        "cms_payment_retry_queue",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("cms_product_order.id"), nullable=False),
        sa.Column("job_type", sa.String(32), server_default="issue_cards", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(80), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", "job_type", name="uq_cms_payment_retry_job"),
    )
    op.create_index("ix_cms_retry_due", "cms_payment_retry_queue", ["status", "next_retry_at"])

    # 4) cms_order_card（多件订单，每张卡独立幂等）
    op.create_table(
        "cms_order_card",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("cms_product_order.id"), nullable=False),
        sa.Column("item_no", sa.Integer(), nullable=False),
        sa.Column("asset_card_id", sa.BigInteger(), sa.ForeignKey("asset_card.id"), nullable=False),
        sa.Column("card_no", sa.String(32), nullable=False),
        sa.Column("credential_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="issued", nullable=False),
        sa.Column("issued_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", "item_no", name="uq_cms_order_card_item"),
        sa.UniqueConstraint("asset_card_id", name="uq_cms_order_card_asset"),
    )
    op.create_index("ix_cms_order_card_order", "cms_order_card", ["order_id"])

    # 5) ReferralCommission 唯一约束补齐（防重复返佣）
    op.create_unique_constraint(
        "uq_referral_commission_order", "referral_commission", ["product_order_id"]
    )


def downgrade() -> None:
    # 严格反向；P0 上线后只在确认无真实交易时执行
    op.drop_constraint("uq_referral_commission_order", "referral_commission", type_="unique")
    op.drop_index("ix_cms_order_card_order", table_name="cms_order_card")
    op.drop_table("cms_order_card")
    op.drop_index("ix_cms_retry_due", table_name="cms_payment_retry_queue")
    op.drop_table("cms_payment_retry_queue")
    op.drop_index("ix_cms_pay_order", table_name="cms_payment_idempotency")
    op.drop_table("cms_payment_idempotency")
    op.drop_index("uq_cms_order_provider_txn", table_name="cms_product_order")
    op.drop_index("ix_cms_order_order_no", table_name="cms_product_order")
    op.drop_column("cms_product_order", "provider")
    op.drop_column("cms_product_order", "paid_at")
    op.drop_column("cms_product_order", "status")
    op.drop_column("cms_product_order", "order_no")
```

#### 关键设计取舍

| 项 | 决策 | 原因 |
|----|------|------|
| 主键 `BigInteger` | SQLite/PG 共用 + `with_variant(Integer, "sqlite")` | 单仓多 DB 兼容，admin 既有表风格 |
| `order_no` 生成 | 前缀 `LEGACY-` + 旧 id（迁移）；新订单 ULID/雪花 | 历史订单无 order_no，迁移可重复；新订单外部可见、不可猜 |
| `(provider, transaction_id)` 部分唯一索引 | `transaction_id IS NOT NULL`（PG）；SQLite 退化为全唯一 | mock 模式 `transaction_id` 为空，不应阻挡 unique |
| `credential_ciphertext` | `TEXT` 存 AES-256-GCM 密文，`CARD_CREDENTIAL_KEY` 独立 secret | 拒绝明文卡密码落库；密钥不进日志、不进 Git |
| `referral_commission.product_order_id` 唯一 | 防止并发回调重复返佣 | P0 缺口二幂等边界硬要求 |
| `cms_payment_retry_queue` 任务表 | 独立表（不入 cms_product_order） | 任务独立状态机、租约、重试次数，便于 poller + 多实例 |
| `ENUM` | **PG 原生 ENUM / SQLite VARCHAR+CHECK** | 单仓双 DB 兼容；ORM 模型用 `String + validators` 抽象 |

#### 落库前 checklist

1. 先在 PG 临时库跑一遍：迁移 → 灌 100 行历史数据（含 `pay_status=paid + quantity=3`）→ 验证回填 + 唯一约束；
2. SQLite 内存库跑一遍：迁移 + 反向迁移 + 再次正向迁移，确认幂等；
3. PG 部分唯一索引的 `postgresql_where` 在 SQLite 上静默忽略，需在 ORM 模型 `__table_args__` 里手工指定；
4. 真实落 alembic 前先 `alembic init alembic` + `env.py` 配 `target_metadata = Base.metadata`，否则 `op.create_table` 找不到外键目标。

---

### §7.20 发卡服务抽离方案（`services/payment_fulfillment.py` · 新建）

#### 现状

`routes/cms/orders.py::_issue_card`（第 97-130 行）是模块内**私有函数**，当前被 `pay_order` 同步调用一次，行为简朴：

```python
async def _issue_card(session, card_type_id) -> tuple[str, str] | None:
    """从 card_type 找 active batch，生成 1 张卡，返回 (card_no, password) 明文"""
    batch = (await session.execute(
        select(AssetCardBatch)
        .where(AssetCardBatch.type_id == card_type_id, AssetCardBatch.status.in_(["draft", "active"]))
        .order_by(AssetCardBatch.id.desc())
    )).scalars().first()
    if not batch: return None
    type_ = await session.get(AssetCardType, card_type_id)
    card_no = "".join(secrets.choice(string.digits) for _ in range(16))
    password = "".join(secrets.choice(string.digits) for _ in range(6))
    unique_code = secrets.token_hex(32)
    base_url = os.getenv("ANTICOUNTERFEIT_BASE_URL", "https://aisport.tech/oa/verify")
    session.add(AssetCard(batch_id=batch.id, type_id=card_type_id,
        card_no=card_no, unique_code=unique_code,
        blockchain_tx_hash=uuid.uuid4().hex,
        qr_url=f"{base_url}/{unique_code}",
        password_hash=hash_password(password),
        face_value=type_.face_value if type_ else 0,
        unit_price=type_.unit_price if type_ else 0, status="issued"))
    batch.generated = (batch.generated or 0) + 1
    if batch.status == "draft": batch.status = "active"
    return card_no, password
```

#### P0 阶段缺口（与 P0 方案文档 §3.4.5 对齐）

1. **数量只 1 张**：`pay_order` 调用一次即 1 张；`quantity=3` 订单只发首张，剩余差额无痕迹；
2. **无行锁**：并发调用同一 batch 可超卖（`generated` 累加无原子保护）；
3. **批次挑选固定按 `id DESC`**：可能挑到旧 draft；应过滤 `status=active` 且 `quantity - generated >= 缺卡数`；
4. **卡密码明文返回**：调用方收到 `(card_no, password)` 直接落 `ProductOrder.issued_card_password` 单值字段，多卡场景无法落地；
5. **无审计 / 无重试**：发卡异常回滚整笔支付事务，与 P0 缺口四"支付事实与履约分层"原则冲突；
6. **无库存预占**：扣减 `batch.generated` 在事务末尾，并发提交下理论可超过 `quantity`。

#### 抽离设计：领域服务 `payment_fulfillment.py`

```
mis-system/services/admin/app/services/payment_fulfillment.py  ← 新建
├─ confirm_payment(session, notification)        # 缺口三：幂等支付确认
├─ issue_order_cards(session, order_id)          # 缺口四：多卡履约
├─ claim_due_jobs(session, limit, worker_id)     # 缺口四：DB poller
└─ _pick_batch_with_stock(session, type_id, need)  # 缺口四：行锁 + 库存校验
```

#### `issue_order_cards` 设计要点

```python
async def issue_order_cards(session: AsyncSession, order_id: int) -> int:
    """为订单补发缺失 item_no 的卡，返回本次新增数量。

    事务边界：
    1. 锁订单 FOR UPDATE（SQLite 退化为 BEGIN IMMEDIATE）
    2. 校验 status ∈ {paid, issuing, fulfillment_failed}
    3. 已发 OrderCard.item_no 集合 vs 1..order.quantity → 缺号
    4. 锁批次 FOR UPDATE + 校验 (quantity - generated) >= 缺数
    5. 循环生成 AssetCard（card_no/unique_code 同旧 _issue_card）
    6. 插入 OrderCard（item_no 1..quantity 全员覆盖由 UK 防重）
    7. 批次 generated += 新增数
    8. 数量齐 → order.status = "fulfilled"，否则 "issuing" 待重试
    9. 落 PaymentRetryJob 状态 succeeded / retry / failed
    10. COMMIT

    调用方：BackgroundTasks + DB poller（lifespan 启停）
    失败重试：指数退避 30s → 2m → 10m → 30m → failed + 告警
    """
```

#### 关键工程要点

| 项 | 抽离前 | 抽离后（`payment_fulfillment.py`） |
|----|--------|-----------------------------------|
| 调用方 | `pay_order` 同步 `await` | webhook ACK 后 `BackgroundTasks.add_task`；poller 兜底 |
| 行锁 | 无 | `with_for_update()` 锁订单 + 锁批次 |
| 数量 | 固定 1 | 按 `order.quantity - len(existing_order_card)` 计算缺号 |
| 卡密码 | 明文返 `issued_card_password` | AES-256-GCM 密文存 `credential_ciphertext`；明文仅 `BackgroundTasks` 返回供前台展示一次 |
| 失败回滚 | 整笔支付事务回滚 | 仅本次卡回滚；订单 `status=issuing` 保持支付事实 `paid` |
| 库存超卖 | 理论可能 | 锁批次 + 校验 `quantity - generated` |
| 重试 | 无 | `cms_payment_retry_queue` 表持久化 + 指数退避 |
| 审计 | 仅日志 | `PaymentRetryJob` + `OrderCard.issued_at` 全链路可追 |

#### 行锁 + 库存校验伪码

```python
async def _pick_batch_with_stock(session, type_id: int, need: int) -> AssetCardBatch:
    # 仅选 active 且库存足够的批次；FOR UPDATE 锁住防并发扣减
    batch = (await session.execute(
        select(AssetCardBatch)
        .where(
            AssetCardBatch.type_id == type_id,
            AssetCardBatch.status == "active",
            AssetCardBatch.quantity.is_not(None),
        )
        .with_for_update(skip_locked=True)
        .order_by(AssetCardBatch.id.desc())
    )).scalars().first()
    if not batch:
        # fallback 允许 draft 自动转 active（兼容 mock 测试）
        batch = (await session.execute(
            select(AssetCardBatch)
            .where(AssetCardBatch.type_id == type_id, AssetCardBatch.status == "draft")
            .with_for_update(skip_locked=True)
            .order_by(AssetCardBatch.id.desc())
        )).scalars().first()
        if not batch:
            raise BatchUnavailable(f"card_type={type_id} 无可用批次")
        batch.status = "active"
    if (batch.quantity - (batch.generated or 0)) < need:
        raise InsufficientStock(f"batch={batch.id} 剩 {batch.quantity - (batch.generated or 0)} < need={need}")
    return batch
```

#### 卡号唯一键冲突重试

`AssetCard.card_no` 有唯一约束。`secrets.choice(digits)` × 16 撞库概率 ~1/10^16，可忽略；但工程上仍包一层：

```python
for attempt in range(3):
    card_no = "".join(secrets.choice(string.digits) for _ in range(16))
    try:
        with session.begin_nested():  # SAVEPOINT
            session.add(AssetCard(card_no=card_no, ...))
            await session.flush()
        break
    except IntegrityError:
        continue
else:
    raise CardNumberExhausted("3 次重试仍冲突")
```

#### 验收（迁移到本服务后）

- `test_cms.py` 新增 6 用例：quantity=3 全发、quantity=3 重跑幂等、并发同 batch 不超卖、批次无库存失败、PaymentRetryJob 5 次耗尽转 `failed`、BackgroundTasks 关闭后 poller 兜底；
- 旧 `_issue_card` 移除，pay_order 在 mock 模式继续走 `confirm_payment(mock_notification)` 走完整服务链路（保持代码同源）；wechat 模式 webhook 入口不再调旧同步路径。

---

### §7.21 notifier 重构方案（`services/notifier.py` · 当前 22 行）

#### 现状盘点

| 项 | 当前 | 问题 |
|----|------|------|
| 超时 | `httpx.AsyncClient(timeout=5)` | 5 秒同步等待，业务响应被通知拖累 |
| 失败处理 | `except Exception: pass` | 静默吞错，无日志无指标 |
| 重试 | 无 | 瞬时故障永久丢通知 |
| 签名 | 无 | 接收方无法验源、防重放 |
| 客户端复用 | 每次新建 | 连接不复用，DNS/TLS 重复开销 |
| 配置刷新 | import 时读 `os.getenv` | 运行时改 env 不生效，须重启 |
| 幂等键 | 无 | 未来补重试将导致接收方重复处理 |
| 死信 | 无 | 长期失败无人工补偿入口 |
| 指标 | 无 Prometheus | 无法观测丢通知率 / 延迟分布 |

#### 重构目标

P0 阶段最小修复 + 后续渐进式升级：

1. **同步→异步**：webhook 调用挪出请求协程，立即返回 200；
2. **客户端复用**：模块级 `httpx.AsyncClient`（连接池复用）；
3. **结构化失败日志**：JSON 行 + `event/id/order_id/latency_ms/error_class`；
4. **`raise_for_status()`**：4xx/5xx 不当成功；
5. **指数退避重试**：30s → 2m → 10m → 30m → 进 dead-letter；
6. **HMAC-SHA256 签名头**：`X-Notify-Signature` + `X-Notify-Timestamp` + `X-Notify-Nonce`；
7. **Prometheus 指标**：`NOTIFY_REQUESTS / NOTIFY_ERRORS / NOTIFY_LATENCY / NOTIFY_DLQ`；
8. **配置热加载**：用 `app.config.settings` 而非 `os.getenv`。

#### 重构后骨架（草案）

```python
# mis-system/services/admin/app/services/notifier.py（重构版）
import asyncio
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import httpx

from app.config import settings  # 热加载；settings.notify_webhook_url 等

_CLIENT: httpx.AsyncClient | None = None
_WORKER: asyncio.Task | None = None
_QUEUE: asyncio.Queue[NotifyEvent] | None = None
_WORKER_ID = f"worker-{secrets.token_hex(4)}"


async def _get_client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=30.0, write=10.0, pool=3.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _CLIENT


def _sign(secret: str, ts: str, nonce: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{ts}\n{nonce}\n".encode() + body, hashlib.sha256)
    return mac.hexdigest()


async def notify(event: str, data: dict, *, event_id: str | None = None) -> None:
    """P0：仅入队，立即返回。接收方凭 event_id 做幂等。"""
    if not settings.notify_webhook_url:
        return  # 未配置完全跳过（保留旧行为）
    ev = NotifyEvent(
        id=event_id or secrets.token_hex(16),
        event=event, data=data,
        enqueued_at=time.time(), attempts=0,
    )
    _QUEUE.put_nowait(ev)
    NOTIFY_REQUESTS.labels(event=event, stage="enqueue").inc()


async def _worker_loop() -> None:
    assert _QUEUE is not None
    while True:
        ev = await _QUEUE.get()
        try:
            await _dispatch(ev)
        finally:
            _QUEUE.task_done()


async def _dispatch(ev: NotifyEvent, *, attempt: int = 1) -> None:
    body = json.dumps({"event": ev.event, "data": ev.data}, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    headers = {
        "Content-Type": "application/json",
        "X-Notify-Event": ev.event,
        "X-Notify-Id": ev.id,
        "X-Notify-Timestamp": ts,
        "X-Notify-Nonce": nonce,
    }
    if settings.notify_signing_secret:
        headers["X-Notify-Signature"] = _sign(settings.notify_signing_secret, ts, nonce, body)

    start = time.time()
    try:
        cli = await _get_client()
        resp = await cli.post(settings.notify_webhook_url, content=body, headers=headers)
        latency = time.time() - start
        NOTIFY_LATENCY.labels(event=ev.event, stage="send").observe(latency)
        if 200 <= resp.status_code < 300:
            NOTIFY_REQUESTS.labels(event=ev.event, stage="ok").inc()
            return
        # 4xx 不重试；5xx 重试
        if 400 <= resp.status_code < 500:
            NOTIFY_REQUESTS.labels(event=ev.event, stage="client_error").inc()
            await _dlq(ev, f"HTTP {resp.status_code}: {resp.text[:200]}")
            return
        raise RuntimeError(f"server_error {resp.status_code}")
    except Exception as exc:
        NOTIFY_ERRORS.labels(event=ev.event, error_class=type(exc).__name__).inc()
        if attempt >= 5:
            await _dlq(ev, f"{type(exc).__name__}: {exc}")
            return
        # 指数退避：30s / 2m / 10m / 30m / 进 DLQ
        delay = [30, 120, 600, 1800][min(attempt - 1, 3)]
        await asyncio.sleep(delay)
        await _dispatch(ev, attempt=attempt + 1)


async def _dlq(ev: NotifyEvent, reason: str) -> None:
    NOTIFY_REQUESTS.labels(event=ev.event, stage="dlq").inc()
    # 写本地 dead_letter.log 或 DB 表（cms_notify_dlq）
    logger.warning(json.dumps({
        "kind": "notify_dlq", "id": ev.id, "event": ev.event,
        "attempts": ev.attempts, "reason": reason,
    }))


async def start_worker() -> None:
    """lifespan 启动时调用：建队列 + worker 协程。"""
    global _QUEUE, _WORKER
    _QUEUE = asyncio.Queue(maxsize=10000)
    _WORKER = asyncio.create_task(_worker_loop(), name="notifier-worker")


async def stop_worker() -> None:
    """lifespan 关闭时调用：drain 队列后取消 worker。"""
    global _WORKER, _QUEUE
    if _QUEUE:
        await _QUEUE.join()
    if _WORKER:
        _WORKER.cancel()
        try:
            await _WORKER
        except asyncio.CancelledError:
            pass
    if _CLIENT:
        await _CLIENT.aclose()
```

#### 风险与边界

- **业务响应**：入队 O(1)，业务接口不再被 webhook 拖累；
- **背压**：队列满时 `put_nowait` 抛 `QueueFull`，调用方可选择 `notify(..., enqueue_blocking=True)` 或直接放弃（YAGNI）；
- **重启丢队列**：未消费的事件在重启时丢失；如需持久化走 `cms_notify_outbox` 表 + poller（同 payment_fulfillment 模式）；
- **接收方去重**：依赖 `X-Notify-Id`，接收方需自行落库去重；
- **签名密钥轮转**：`settings.notify_signing_secret` 变更后旧事件仍按旧 key 签；接收方应支持多 key 并行校验。

#### Prometheus 指标定义

| 指标 | 类型 | label | 含义 |
|------|------|-------|------|
| `notify_requests_total` | Counter | `event` / `stage` | enqueue / ok / client_error / dlq |
| `notify_errors_total` | Counter | `event` / `error_class` | 异常分类 |
| `notify_latency_seconds` | Histogram | `event` / `stage` | 端到端发送耗时 |
| `notify_dlq_total` | Counter | `event` | 死信累计 |

#### 与 P0 关系

notifier 升级独立于 P0 支付 webhook（P0 是入站回调，notifier 是出站通知）；二者共用队列/重试/指标模式，但失败不互相牵连。`pay_order` 在业务 commit 后调用 `notify()` 即丢入队，不阻塞。

---

### §7.22 STS 注入点（`services/storage/cos.py` + `services/storage/sts.py` · 当前 YAGNI）

#### 当前状态

`CosStorage.__init__` 直接在 `__init__` 阶段把 `secret_id / secret_key` 塞进 `CosConfig`，构造一次性完成，**之后无法轮换凭据**：

```python
# cos.py L78-107（现状）
def __init__(self, *, region, secret_id, secret_key, bucket, scheme="https", timeout=60.0):
    ...
    CosConfig, CosS3Client = _try_import_cos_sdk()
    config = CosConfig(
        Region=region, SecretId=secret_id, SecretKey=secret_key,
        Scheme=scheme, Timeout=int(timeout),
    )
    self._client = CosS3Client(config)
```

Long-Term Key 风险：

- **凭据散落**：CAM 子账号 AK/SK 静态写在 env，进程长跑期间无法轮换；
- **泄漏面**：任何一处日志/异常/dump 包含 config repr 即泄漏；
- **多租户**：未来若要给不同 bucket/业务开不同子账号，凭据硬绑 init 阶段。

#### STS 改造路径（YAGNI 当前不动，**注入点已就位**）

`sts.py` 已存在 `STSCredentialProvider` 抽象（参见 `project-sprint0-storage-2026-07-14.md`），未来启用时仅需在 `CosStorage.__init__` 增加 1 个可选参数：

```python
def __init__(
    self,
    *,
    region: str,
    bucket: str,
    scheme: str = "https",
    timeout: float = 60.0,
    # ── 凭据注入（互斥）：long-term 直接传 / sts provider 注入
    secret_id: str | None = None,
    secret_key: str | None = None,
    sts_provider: STSCredentialProvider | None = None,
):
    if not region: raise InvalidArgument("CosStorage 缺 region")
    if not bucket: raise InvalidArgument("CosStorage 缺 bucket")

    self.region = region
    self.bucket = bucket
    self.scheme = scheme

    # 凭据获取策略：STS 优先；fallback long-term
    if sts_provider is not None:
        creds = sts_provider.fetch()  # {"SecretId": "...", "SecretKey": "...", "Expiration": "..."}
        self._secret_id = creds["SecretId"]
        self._secret_key = creds["SecretKey"]
        self._sts_provider = sts_provider
    elif secret_id and secret_key:
        self._secret_id = secret_id
        self._secret_key = secret_key
        self._sts_provider = None
    else:
        raise InvalidArgument("CosStorage 需 secret_id/secret_key 或 sts_provider")

    CosConfig, CosS3Client = _try_import_cos_sdk()
    self._client = self._build_client(CosConfig, CosS3Client)
```

#### 客户端重建钩子（动态轮换）

STS 临时凭证有效期通常 1-2 小时，**过期前必须重建 `CosS3Client`**。建议在 `presigned_upload` / `_call` 调用前检查：

```python
def _ensure_fresh_credentials(self, CosConfig, CosS3Client) -> None:
    """STS 模式：在凭证过期前 5 分钟重建 client。"""
    if self._sts_provider is None:
        return  # long-term 不轮换
    if not self._client or self._creds_about_to_expire():
        creds = self._sts_provider.fetch()
        self._secret_id = creds["SecretId"]
        self._secret_key = creds["SecretKey"]
        self._client = CosS3Client(CosConfig(
            Region=self.region, SecretId=self._secret_id,
            SecretKey=self._secret_key, Scheme=self.scheme,
            Timeout=int(self._timeout),
        ))
        COS_TOKEN_ROTATIONS.inc()
```

`_call` / `presigned_upload` / `presigned_download` 入口都加一行 `self._ensure_fresh_credentials(...)` 即可。

#### 启用判定

| 条件 | 决策 |
|------|------|
| 单租户 / 单 bucket / 单 sub-account | **保持 Long-Term Key**（当前） |
| 多租户 / 多 bucket / 凭证需定期轮换 | 启用 STS |
| 前端直传 presigned URL 需分用户签发 | 启用 STS（不同用户拿不同临时 key） |

`project-sprint0-storage-2026-07-14.md` 已记录用户决策：**复用 qmwx-cos-uploader 子账号不新建**（STS 暂缓 YAGNI，代码零改动吃长密钥）；故当前 §7.22 **仅作注入点设计存档**，不实施。

#### 验收（如未来启用）

- `tests/integration/test_cos_integration.py` 新增 3 用例：STS 过期前自动轮换、STS provider 失败重试、长期 Key 模式兼容；
- `services/storage/cos.py` 构造函数签名变更需保留向后兼容（旧 `secret_id/secret_key` 调用方零改动）；
- `services/storage/sts.py` 需补 `LocalSTSCredentialCache`（避免每次 IO 都调 STS API）；
- COS 子账号 CAM 策略升级为允许 `sts:AssumeRole`（最小权限 + 限定 source ip）。

#### 与 P0 关系

P0 支付 webhook 不涉及对象存储；STS 改造与 P0 完全独立。本节仅为后续若启用多租户 / 子账号分桶 / 前端分用户直传签名等场景的"零成本预埋"参考。
- **`STORAGE.md`**（🆕，`mis-system/docs/` 下）— Storage 抽象层 + 腾讯云 COS 决策

---

## §7.23 P0 支付 Day 1/2 实际落地与未闭环项（2026-07-15 Day 1 + 2026-07-16 Day 2 部分）

### Day 1 已落地（commits ee38d06/ea98719/9b3c3e6/e9aeaa3）

- **alembic 架构级引入**（admin 此前完全靠 `init_db()` 自动建表，无迁移历史）：`alembic.ini` / `alembic/env.py` / 首个 revision `20260715_cms_payment_webhook_p0`；
- **3 张新表**：`cms_payment_idempotency`（11 列，部分唯一索引 `WHERE payment_id IS NOT NULL`）/ `cms_webhook_retry`（10 列，`idx_..._status ON (status, next_retry_at)`）/ `cms_order_card`（4 列，简化无 item_no/credential_ciphertext）；
- **ProductOrder 7 状态机**：`status` 字段 `String(20) nullable=True server_default='pending'` + PG native ENUM `cms_order_status`（SQLite 退化为 String(20)）+ `effective_status`/`is_paid` 2 个 hybrid_property；
- **pay_status 兼容窗口**：保留到 2026-09，`effective_status` 自动从 pay_status 回退；
- **微信支付配置 + 4 新依赖**：`.env.example` +18 行（`PAYMENT_PROVIDER`/`WECHAT_PAY_*`）；`requirements.txt` +7 行（alembic/wechatpayv3/pycryptodome/cryptography）；
- **263 行状态机测试**：`tests/test_product_order_status.py` 6 组（默认值/effective_status 优先级/7 值可写/is_paid/列存在性/端到端生命周期）。

### Day 2 已部分落地（未提交到 mis-system HEAD e9aeaa3，工作树现状）

- **`services/wechat_pay.py::WechatPayV3Gateway`**：回调 RSA-SHA256 验签 + ±300s 时间窗 + AES-256-GCM 解密 + `WechatNotify` DTO；**下单/退款/查单仍 `NotImplementedError`**；
- **`services/payment_fulfillment.py`**（新建）：`confirm_payment()`（金额分校验 + 订单行锁 + 支付幂等 + 状态双写 + 优惠券/返佣）+ `issue_order_cards()`（多卡补发 + 批次行锁 + 单次 flush + 可重入）+ `WebhookRetry` 入队/退避/poller；
- **`routes/cms/payments.py`**：由 14 行占位改为完整微信回调链路（验签→解密→幂等确认→发卡任务入队→BackgroundTasks→ACK）；
- **`main.py::lifespan`**：启动 DB poller（WebhookRetry 后台扫描）；
- **`routes/cms/orders.py::pay_order`**：已复用 `confirm_payment()` 与 `issue_order_cards()`；
- **新测试**：`tests/test_wechat_pay.py` 7 项 + `tests/test_payment_fulfillment.py` 12 项（支付确认/幂等/金额/优惠券/多卡/库存/任务重试）。

### Day 2 仍未闭环的 5 项 critical 缺口（**生产接入前必修**）

1. **`set_gateway()` 未注入 lifespan**：全局 `gateway` 仍是 `MockGateway`；若只配置 `PAYMENT_PROVIDER=wechat`，同步 `/orders/{id}/pay` 会把 mock 成功标为 wechat 支付事实，**必须 fail-closed**；
2. **平台证书 X.509 解析缺**：`WECHAT_PAY_PLATFORM_CERT_PATH` 当前通过 `load_pem_public_key()` 读取，若文件是真正 X.509 平台证书将无法解析；同时未读取/校验 `Wechatpay-Serial`，不支持平台证书轮换选择；
3. **`parse_notify()` 异常未映射安全 4xx**：JSON/字段/AES 解密异常未统一映射为 4xx；**缺 payments 路由级回调测试**；
4. **异常事件未持久化/告警**：微信支付确认冲突仅 ACK + 日志，未持久化异常事件/告警；重试耗尽仅把 job 置 `failed`，**未同步订单 `failed`、未告警**；`locked_at`/租约回收尚未启用；
5. **mock 同步发卡失败无持久化重试**：仅返回 `issue_pending`，未创建持久化重试任务；真实 Native 下单/退款/查单 与 小额真单灰度**仍待商户资料**（`WECHAT_PAY_MCH_ID/APP_ID/API_V3_KEY`）。

### §7.19-§7.22 草案 vs Day 1 实际偏差表

| 维度 | §7.19 草案（pre-impl） | Day 1 实际 |
|------|------------------------|------------|
| 重试队列表名 | `cms_payment_retry_queue` | `cms_webhook_retry` |
| 重试队列列 | job_type/max_attempts/locked_by/completed_at | 仅 attempts/next_retry_at/locked_at（更简） |
| 幂等表 provider 列 | `provider` | `payment_provider` |
| 幂等表 txn 列 | `transaction_id`/`event_id`/`event_type` | `payment_id`（nullable，无 event_id/event_type） |
| 幂等唯一约束 | `UNIQUE(provider, event_id)` + `UNIQUE(provider, txn)` | **部分唯一索引** `WHERE payment_id IS NOT NULL` |
| order_card 列 | item_no/credential_ciphertext/card_no/status/issued_at | 仅 order_id/card_id/created_at（多卡关联，无密文） |
| order_no 字段 | 新增 + ULID/雪花 | **未新增** |
| ReferralCommission UK | 补唯一约束 | **未补** |
| status nullable | NOT NULL | **nullable=True** |
| DROP pay_status | 后续移除 | **Day 1.1.1 明确保留** + 兼容窗口到 2026-09 |
| 方言策略 | 笼述 PG ENUM/SQLite CHECK | **PG native ENUM `cms_order_status` / SQLite String(20)** + `_dialect_name()` 强校验 |

> ⚠️ **§7.19-§7.22 是 P0 实施前设计草案存档**，与实际 Day 1/Day 2 落地有上述偏差，**以实际代码为准**。Day 2 实际代码多处未对照草案细化（例如 `payment_fulfillment.py` 已建，但与 §7.20 草案的"卡密码 AES-GCM 密文"+"卡号唯一键冲突重试"等细节未完全对齐，待 Day 2.5 校准）。

### 36 项审计代码 vs 记忆偏差 4 处（2026-07-16 核对）

| # | 路径 | 记忆描述 | 代码现状 | 影响 |
|---|------|----------|----------|------|
| 1 | `routes/auth.py` | 登录限流 | **未见显式登录限流**，仅 register 有 | 暴力破解风险（需补 limiter） |
| 2 | `routes/auth.py` | 注册阈值 5/小时 | **实际 1000/小时，注释写 5/小时** | 文档/注释与代码脱节（需修注释） |
| 3 | `tests/conftest.py` | session token 缓存 | **每测试重新登录**，未见缓存 | 测试性能下降，无功能影响 |
| 4 | `app/main.py::lifespan` | `notifier.close_client()` 挂 shutdown | **未挂接** | httpx 连接池泄露（shutdown 时未关闭） |

---

## §7.24 TripGen 子域（2026-07-16 新增 admin 内部子域）

### 定位

**TripGen 是 admin 内部子域**（不单独生成模块 CLAUDE.md），提供"AI 设计行程 + 多格式产物导出"能力。Trip 模型为**单一数据源**，可派生 HTML、正文 PDF、图文 PDF、合并 PDF 四类产物。

### 入口

- **HTTP API**：`app/routes/tripgen.py`
  - `GET /admin/api/v1/tripgen/example` — 返回样例 Trip 数据（调试用）
  - `POST /admin/api/v1/tripgen/preview` — 预览（不写入磁盘）
  - `POST /admin/api/v1/tripgen/generate` — 生成并返回服务器临时路径
- **CLI**：`app/cli/tripgen.py`（与 HTTP 共用 service 层）
- **数据/流水线**：`app/services/tripgen/`（11 个一方文件：pipeline/models/html_guide/pdf_body/...）

### 核心设计

- **Trip 单一数据源**：Day × N 行程节点 + 主题/季节/目的地/费用 4 类元数据；
- **四类产物**：① HTML 指南（无需依赖）② 正文 PDF（reportlab）③ 图文 PDF（weasyprint + 中文字体）④ 合并 PDF（pypdf）；
- **降级策略**：reportlab/weasyprint/pypdf 缺失时返回 HTML 或抛 503；
- **依赖检测**：启动时 sniff 三套库是否可用，按能力组合提供服务；
- **CLI 与 HTTP 共用 pipeline**：避免双实现漂移。

### 当前未闭环风险

- `generate` 返回**服务器临时绝对路径**，无 `/download` 接口、无 COS URL、无 TTL、无临时目录清理；
- PDF 特殊依赖分支覆盖不足（`test_tripgen.py` 对 PDF 链低覆盖）；
- 前端目前**未见 TripGen UI**（`apps/web/src/views/` 无 tripgen 目录），CLI 是唯一入口。

### 关键文件

- `app/routes/tripgen.py` — 3 API 路由
- `app/services/tripgen/pipeline.py` — 主流水线
- `app/services/tripgen/models.py` — Trip + Day + Node + Metadata
- `tests/test_tripgen.py` — 主要测试
- `tests/test_coverage_extra.py` — 补充覆盖

---

## §7.25 Office Engine 本地引擎（2026-07-16 与 oa-agent bridge 共用 routes/office.py）

### 定位

**Office Engine 是 admin 内部子域**，与 oa-agent 桥**共用** `app/routes/office.py`（11 端点 = 6 个 oa-agent 桥 + 5 个本地引擎）。oa-agent 是远程文档能力中心（docx_to_html / merge_template / read_*）；本地引擎补齐 PDF / Excel / PPTX / 模板填充 / 批处理 5 类重 CPU 操作。

### 入口

- **`app/services/office/engine.py`** — 6 核心函数：
  1. `docx_to_pdf(input_path)` — docx → PDF（libreoffice/docx2pdf）
  2. `html_to_pdf(html)` — HTML → PDF（weasyprint）
  3. `json_to_excel(data)` — JSON → xlsx（openpyxl）
  4. `data_to_pptx(data)` — 数据 → pptx（python-pptx）
  5. `fill_template(template, vars)` — 模板填充（docxtpl/jinja2）
  6. `batch_process(jobs)` — 批处理编排（多产物并发）
- **`app/routes/office.py`** — 11 端点：
  - 6 桥端点：`/office/{health,tools,read,preview,merge}/...`（透传 oa-agent `/tools/{name}`）
  - 5 本地端点：`/office/pdf`、`/office/excel`、`/office/pptx`、`/office/form`、`/office/batch`

### 当前未统一风险

- **workspace 沙箱未统一**：本地 5 端点共用 `template/input_dir/output_dir` 但**无统一 workspace 边界校验**；
- **重 CPU 同步阻塞**：PDF/PPT/Excel 同步任务直接跑在 async 路由中（未卸载到线程池/任务队列）；
- **临时文件无生命周期**：未设 TTL、未自动清理，磁盘可能累积；
- **特殊依赖分支覆盖不足**：`test_coverage_extra.py` 对 weasyprint/pptx/openpyxl 缺失分支覆盖低。

### 与 oa-agent 桥的边界

| 能力 | oa-agent 桥（远程） | 本地引擎 |
|------|---------------------|----------|
| docx 预览 | ✅ mammoth → html | ❌ |
| 模板合并 | ✅ docxtpl | ✅ 通用 fill_template |
| docx 读取 | ✅ read_docx | ❌ |
| docx → PDF | ❌ | ✅ docx_to_pdf |
| HTML → PDF | ❌ | ✅ html_to_pdf |
| Excel 生成 | ❌ | ✅ json_to_excel |
| PPTX 生成 | ❌ | ✅ data_to_pptx |
| 批处理 | ❌ | ✅ batch_process |

### 关键文件

- `app/services/office/engine.py` — 6 核心函数
- `app/services/office/bridge.py` — oa-agent 桥
- `app/routes/office.py` — 11 端点
- `app/cli/office.py` — CLI（与 HTTP 共用 service 层）
- `tests/test_office.py` + `tests/test_office_bridge.py` + `tests/test_coverage_extra.py`

---

## §7.26 P0 Day 2 实施闭环（2026-07-16 commit `a530537` 收官）

### 4 项 critical 缺口全部修复

| # | 缺口 | Commit | 关键改动 | 测试 |
|---|---|---|---|---|
| 1 | `set_gateway()` 未注入 lifespan (fail-closed) | `3b82c55` | `build_gateway_from_settings` 4 路径 (mock/wechat/alipay/unknown) + lifespan fail-closed raise (systemd 非零退出) | 14 新 + 66 P0 回归 |
| 2 | WECHAT_PAY_PLATFORM_CERT_PATH X.509 解析 + Wechatpay-Serial | `308199f` | `cryptography.x509.load_pem_x509_certificate` + 3 种加载 (platform_certs dict / platform_cert_dir / platform_cert_path) + `verify_callback` Serial 校验 | 10 新 + 21 回归 |
| 3 | parse_notify 异常未统一映射安全 4xx | `45ac695` | 7 个业务异常类 (WechatNotifyError 基类 + 6 子类 http_status 401/400/409) + `parse_notify_safe` 分阶段 raise + Redis NX 重放检测 + 路由异常映射 | 10 新 + 77 回归 |
| 4 | 异常持久化 + 告警 + locked_at 租约 | `08835b7` | `claim_pending_jobs` SELECT FOR UPDATE SKIP LOCKED + 5min 租约 + `PaymentExceptionEvent` 表 + 3 Prometheus 指标 + 同步订单 failed + alembic revision `20260715_cms_payment_exception_event_p1` | 10 新 + 12 回归 |

### 第 5 项缺口（mock 同步发卡失败持久化 + 真 Native pay/refund/query）

⏸ **未做 — 需商户资料**：`WECHAT_PAY_MCH_ID/APP_ID/API_V3_KEY`。
Gateway fail-closed 已就绪（commit 3b82c55），配置补齐后即可实施。

### 关键设计决策

- **P0 #1 fail-closed（拒绝启动）**：资金关键路径静默降级比显式崩溃更危险；systemd restart loop 立即可见
- **P0 #4 SKIP LOCKED + locked_at 租约**：多实例 worker 不重复处理，5 分钟默认租约可重领过期
- **P0 #3 异常类分层**：基类 `http_status=400` 默认 + 子类覆盖（401 鉴权 / 409 重放 / 400 内容），路由 `except WechatNotifyError as e` 兜底用 `e.http_status`

### B + C 自动合并奇迹

Agent B (308199f X.509) + Agent C (45ac695 parse_notify) **都修改 `app/services/wechat_pay.py`**：
- B 改顶部（证书加载 + verify_callback，+223 行）
- C 改中下部（7 异常类 + parse_notify_safe，+184 行）
- git 自动合并成功，**零 conflict**
- 最终 `wechat_pay.py` 530 行，两套功能完美共存

---

## §7.27 test isolation 误诊修正 + TripGen lazy import + 测试基线重置

### TripGen lazy import（commit `d8dc562`）

#### 回归 bug

round-6 合并 `0fa4469` 引入：
- `app/services/tripgen/__init__.py` 顶层 `from . import config, pipeline, models`
- `pipeline.py` 顶层 `from . import fonts, pdf_body, html_guide, merge`
- 这些子模块在模块顶层 `import reportlab` / `weasyprint` / `pypdf`
- 导致 `tests/conftest.py::from app.main import app` 直接挂
- **整个 admin 测试套件无法启动**（所有测试"挂"）

#### 修复

按 §7.24 设计意图"字体/weasyprint 缺失时降级"：
- `__init__.py` 仅导出 `config` + `models`（不导入 pipeline）
- `pipeline.py` 用 `importlib.import_module(f".{name}", __name__)` 动态加载 PDF 子模块
- 缺 PDF 库时跳过对应步骤：
  - 缺 reportlab → 跳过正文 PDF
  - 缺 weasyprint → 跳过图文 PDF
  - 缺 pypdf → 跳过合并
  - 中文字体缺失 → 跳过正文 PDF
- HTML 攻略总是先产出（不依赖 PDF）

#### 教训

**新模块导入必须 lazy import**：
- 测试 fixture `from app.main import app` 会触发所有顶层 import
- 子模块硬依赖可选库 → 整个测试套件挂掉
- 必须 lazy import + fail-soft（运行时按需加载 + 缺包优雅降级）

### Test isolation 误诊修正（commit `a530537`）

#### 历史误判

之前几轮报告的 "128 errors / 16 failed test isolation 问题" 是**历史状态**，**已被完全消除**。
当前实测 6 种 isolation 模式（fixture 缺失 / db 污染 / 导入污染 / session 泄漏 / 顺序依赖 / event loop 冲突）一一核查均无。

#### 根因（conftest 设计）

```python
@pytest.fixture(scope="session")
def client():
    """会话级 TestClient（lifespan 触发 init_db + seed admin/admin1234）"""
    with TestClient(app) as c:
        yield c
    # 清理测试库
    for p in ("./test.db",):
        if os.path.exists(p):
            os.remove(p)

@pytest.fixture  # 默认 function scope
def auth_header(client):
    """登录拿 token"""
    r = client.post("/admin/api/v1/auth/login",
                    json={"username": "admin", "password": "admin1234"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

**鲁棒三件套**：
1. `lifespan` 幂等（`init_db` + `seed_initial_data` 内有 if-not-exists 判断）
2. `seed_initial_data()` 内部 if-not-exists 防止重复
3. 函数级 `auth_header`（不污染 session client）

#### 真正的剩余 3 个 fail = 环境依赖

| 测试 | 根因 | 修复 |
|---|---|---|
| `test_data_to_excel_dict_rows` + `test_data_to_excel_list_rows_with_headers` | 缺 `openpyxl` | `pip install openpyxl` + `requirements.txt` 加 `openpyxl>=3.1` |
| `test_html_to_pdf_or_skip` | macOS 缺 `libgobject-2.0-0` (GTK 系统库) | 测试 `except ImportError` → `except (ImportError, OSError)` |

### 测试基线重置

```
PYTHONPATH=. python -m pytest tests/ -q --tb=short
→ 418 passed, 8 skipped, 0 failed in 283.69s (0:04:43)
```

| 维度 | 历史 | 本轮末 |
|---|---|---|
| passed | 191 (7-14) / 245 (7-15) / 372 (7-15 round5) | **418** |
| failed | 5 pre-existing | **0** |
| skipped | n/a | **8** (weasyprint/pptx 等可选依赖) |
| isolation issues | 128 errors / 16 failed (误诊) | **0** |
| 跑全套耗时 | 285s | **283.69s** (基本持平) |

### 10 个 Deprecation Warnings

`datetime.utcnow()` 10 处需要改为 `datetime.now(datetime.UTC)`（Python 3.12+ 弃用，不影响功能）：
- `app/routes/cms/auth.py:30` (1 处)
- `tests/test_product_order_status.py:236` (1 处)
- 其他散落位置待 grep

### 教训

1. **pre-existing 报告需重新验证**：本轮 init-architect 报告的 "test isolation 128 errors" 是**误诊**，36 项审计已修复
2. **session client + 测试文件 db 设计鲁棒**：lifespan 幂等 + seed if-not-exists + 函数级 auth_header 三件套保证测试间不污染
3. **pytest 跑全套 4:43 瓶颈**：session client + SQLite 文件 I/O + lifespan 重启；未来可用 pytest-xdist 并行（但需改 worker 级 teardown）

---

## 变更记录 (Changelog)

- 2026-07-16 (后续 commit 闭环) — P0 Day 2 4 项 critical 缺口修复全部 commit + TripGen lazy import + test isolation 误诊修正：
  - **新增 §7.26** P0 Day 2 实施闭环 — 4 项 critical 缺口 commit 表（308199f X.509 / 3b82c55 set_gateway fail-closed / 45ac695 parse_notify 4xx / 08835b7 异常持久化+租约）+ 第 5 项缺口需商户资料 + 关键设计决策（fail-closed / SKIP LOCKED / 异常类分层）+ B+C 自动合并奇迹；
  - **新增 §7.27** TripGen lazy import + test isolation 误诊修正 + 测试基线重置 418/0/8 + 10 个 datetime.utcnow() DeprecationWarning；
  - **mis-system HEAD = a530537**，ahead of origin/main 16 commits；
  - **P0 真支付 P0 Day 2 critical 缺口 4/5 完成**——仅 #5 真 Native API 等商户资料；
  - **教训**：lazy import 设计原则（新模块默认 lazy）+ pre-existing 报告需重新验证（test isolation 误诊）+ parallel agent git 自动合并（B+C wechat_pay.py）。
- 2026-07-16 13:42:20 — admin 文档校准（第六轮 init-architect + general-purpose 追加）：
  - **新增 §7.23 P0 支付 Day 1/2 实际落地与未闭环项**：落地清单 + 5 项 critical 缺口 + §7.19-§7.22 草案 vs 实际偏差表（详见 §7.23）；
  - **新增 §7.24 TripGen 子域**：Trip 单一数据源、3 API、HTML/PDF/图文/合并 PDF 四类产物、降级策略、临时路径未闭环风险（详见 §7.24）；
  - **新增 §7.25 Office Engine 本地引擎**：6 核心函数、5 本地端点、与 oa-agent 桥的边界、workspace 沙箱/线程池/临时文件未统一风险（详见 §7.25）；
  - **36 项审计代码 vs 记忆偏差 4 处**（详见 §7.23 末尾）：登录限流缺 / 注册阈值注释错 / conftest session 缓存缺 / notifier.close_client 未挂 lifespan；
  - 顶部 Changelog 与底部变更记录同步；不修改 §7.19-§7.22 草案存档。
- 2026-07-15 14:00:00 — P0 实施前精细深读（第五轮）：
  - **§7.19 P0 Day 1.1 alembic migration 详解**：草案 `20260715_cms_payment_webhook_p0.py`（admin 服务尚未启用 alembic，先 `alembic init` + 配 `env.py`）；含 ProductOrder status 迁移 + cms_payment_idempotency / cms_payment_retry_queue / cms_order_card 三张新表 + ReferralCommission 唯一约束；SQLite/PG 双兼容 + 部分唯一索引 `postgresql_where`；
  - **§7.20 发卡服务抽离方案**：新建 `services/payment_fulfillment.py` 领域服务（confirm_payment / issue_order_cards / claim_due_jobs / _pick_batch_with_stock）；行锁 + 库存校验 + 多卡 item_no 幂等 + 卡密码 AES-GCM 密文 + 卡号唯一键冲突重试；旧 `_issue_card` 同步路径作废；
  - **§7.21 notifier 重构方案**：模块级 httpx.AsyncClient 复用 + asyncio.Queue worker + HMAC-SHA256 签名（X-Notify-Signature/Timestamp/Nonce）+ 4 级指数退避 30s/2m/10m/30m + dead-letter + Prometheus 4 指标；P0 阶段仅入队 O(1) 立即返回，业务不被通知拖累；
  - **§7.22 STS 注入点**：CosStorage.__init__ 增加 sts_provider 可选参数 + _ensure_fresh_credentials 轮换钩子；当前 YAGNI 保留注入点不实施（qmwx-cos-uploader 长密钥策略已落定）。
- 2026-07-15 11:42:03 — 续跑增量更新（zcf:init-project）Sprint 0/1/2 收官 + 财务复式 + 工作台拖拽 + dy8 部署（详见上方 Changelog 索引，文件顶部）。
- 2026-07-15 — office 桥全链路打通 + dev proxy 修复（详见 memory `project-officecli-bridge-2026-07-14.md`）。
- 2026-07-14 14:54:32 — 续跑增量更新 CMS 模块全完成 + 全栈审查 + mlx-asr 测试补齐 + 前端 any 159→87。
- 2026-07-13 10:58:44 — 续跑增量更新 路径修正 + 测试全景更新。
- 2026-07-12 16:08:16 — 新增根级 CLAUDE.md（zcf:init-project 续跑）。
- 2026-07-12 15:55:11 — 初始化 AI 上下文（zcf:init-project）。