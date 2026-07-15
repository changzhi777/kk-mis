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
- **`cms-content-module-research.md`**（🆕，`mis-system/docs/` 下）— CMS 架构决策与设计文档
- **`STORAGE.md`**（🆕，`mis-system/docs/` 下）— Storage 抽象层 + 腾讯云 COS 决策