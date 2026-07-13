# VIP 卡定价 + 区域代理返佣规则（决策 #3 重构 2026-07-13）

> **目的**：业务规则独立文档，便于产品/销售/法务随时查阅，避免翻代码猜细节。

## 一、VIP 卡定价

### 1.1 标准单价

| 项目 | 数值 |
|---|---|
| VIP 单卡标准单价 | **¥1,888.00** |
| 可被覆盖 | `AssetCardBatch.unit_price`（批次级） |
| 可被覆盖 | `AssetCardType.unit_price`（类型级，默认同上） |
| 环境变量 | `VIP_CARD_UNIT_PRICE`（仅启动日志提示，不改逻辑） |

### 1.2 数量阶梯折扣

| 进货数量 | 折扣 | 单价（按标准 ¥1888） | 适用场景 |
|---|---|---|---|
| 1-99 张 | 7 折 | ¥1,321.60/张 | 试销 / 体验装 |
| 100-999 张 | 6 折 | ¥1,132.80/张 | 中等规模代理首单 |
| 1000+ 张 | 5 折 | ¥944.00/张 | 旗舰代理大批量 |

**计算位置**：`POST /api/v1/agent/orders/quote` 实时报价（不下单）/ `POST /api/v1/agent/orders` 创建订单自动应用

**前端预览位置**：`OrderList.vue` 创建订单弹窗的"实时折扣预览"

### 1.3 折扣合规边界

- 折扣作用于 `unit_price`，不影响 `commission_rate`
- `commission_rate` 上限 ≤ 0.5（决策 #3 合规边界保留）
- 防全额返利：阶梯折扣最高 5 折；年度返佣最高 50%（合计 50% 上限）

---

## 二、区域代理模式（推翻原 3 级代理）

### 2.1 结构

| 维度 | 旧（3 级分销） | 新（区域代理） |
|---|---|---|
| 层级 | level 1/2 + parent_id | 平级（无层级） |
| 划分维度 | 代理上下级 | 地理区域 `region_code` |
| 同 region 唯一 | — | ✅（同 region_code 仅 1 个 active agent） |
| 销售范围 | 全局 | 仅本 region（区域代理核心特征） |
| 业绩归属 | 按层级继承 | 区域独占 |

### 2.2 字段

```python
class Agent:
    region_code: str    # 如 'SH' / 'BJ' / 'GZ'（必填）
    region_name: str    # 如 '上海'（可选）
    commission_rate: Decimal  # ≤ 0.5（合规上限）
    status: bool
```

**已废弃字段**（兼容旧 commission_records 但不再使用）：
- ~~`level`~~ — 去掉
- ~~`parent_id`~~ — 去掉
- ~~CommissionRule.rate by level~~ — 仍存在但不再按 level 配率

### 2.3 默认数据（seed.py）

- 上海（SH） / 北京（BJ） / 广州（GZ） 三个区域代理
- 每个绑定 admin 用户，commission_rate = 30%

---

## 三、年度累计返佣（双层返佣的第二层）

### 3.1 阶梯规则

| 阶梯 | 年度累计销售额 | 返佣比例 |
|---|---|---|
| T1 | < 50 万 | **30%** |
| T2 | 50-200 万 | **40%** |
| T3 | > 200 万 | **50%** |

**计算位置**：`POST /api/v1/agent/yearly-commission/settle?year=YYYY`

### 3.2 触发时机

- 每年 1 月初（建议 cron / systemd timer）
- 手动触发（admin 触发测试）
- dry_run=true 只计算不写库（用于预览）

### 3.3 与单次折扣叠加

| 场景 | 单次折扣 | 年度返佣 | 最终返佣 |
|---|---|---|---|
| 100 张 VIP（6 折），年度累计 10 万 | 节省 ¥75,520 | T1 30% = ¥39,840 | ¥39,840 现金 + 折扣 |
| 1000 张 VIP（5 折），年度累计 200 万 | 节省 ¥944,000 | T3 50% = ¥944,000 | 仅 T3，**无叠加** |
| 1000 张 VIP（5 折），年度累计 100 万 | 节省 ¥944,000 | T2 40% = ¥400,000 | ¥400,000 现金 + 折扣 |

**关键**：单次折扣（5 折起）作用于订单；年度返佣作用于**当年累计销售额**。两者**不叠加比例**（不超出 50% 上限）。

---

## 四、防伪技术（Phase 1 mock + Phase 2 链上）

### 4.1 字段

```python
class AssetCard:
    unique_code: str          # 64 位 hex（系统生成，secrets.token_hex(32)）
    blockchain_tx_hash: str   # Phase 1 mock = uuid hex；Phase 2 接 Fabric
    qr_url: str               # 形如 https://aisport.tech/oa/verify/{unique_code}
    last_verified_at: datetime
```

### 4.2 QR 内容

- 扫码跳转：`{ANTICOUNTERFEIT_BASE_URL}/{unique_code}`
- 默认 URL：`https://aisport.tech/oa/verify`
- 可配置：env `ANTICOUNTERFEIT_BASE_URL`

### 4.3 核销接口

```
GET /api/v1/asset/cards/verify/{unique_code}    [公开，无需登录]
```

**Phase 1 mock 响应**：
```json
{
  "verified": true,
  "unique_code": "abcd...64位hex",
  "card_no_prefix": "1234****5678",
  "batch_id": 1,
  "type_id": 1,
  "status": "issued",
  "blockchain_tx_hash": "uuid",
  "last_verified_at": null
}
```

**Phase 2 Fabric**：调用 chaincode `verifyCard(unique_code)` 对账后返回 verified。

---

## 五、合规边界（合规审计必查项）

| 风险 | 防护 | 验证 |
|---|---|---|
| 全额返利（传销特征） | `commission_rate ≤ 0.5` + 阶梯折扣最高 5 折 | `test_pricing.py::test_compute_vip_discount_*` |
| 3 级分销（传销边缘） | 已去除 level/parent_id，平级区域代理 | `test_agent.py::test_duplicate_region_code_rejected` |
| 全额返利违规 | `MAX_COMMISSION_RATE = Decimal("0.5")` pydantic 校验 | `test_config_validation.py::test_*_50_percent` |
| 区域撞车 | 同 region_code 唯一约束 | `test_vip_orders.py::test_duplicate_region_code_rejected` |
| 卡券伪造 | 64 位 unique_code + QR + 防伪核销 | `test_anticounterfeit.py::test_*` |

---

## 六、API 速查

| 路径 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/api/v1/agent/orders/quote` | GET | agent:order:list | 实时折扣报价（不下单） |
| `/api/v1/agent/orders` | POST | agent:order:save | 创建订单（自动应用折扣） |
| `/api/v1/agent/orders/{id}/pay` | POST | agent:order:save | 确认付款 |
| `/api/v1/agent/orders/{id}/complete` | POST | agent:order:save | 完成订单（触发单次返佣） |
| `/api/v1/agent/yearly-commission` | GET | agent:commission:view | 查询年度返佣 |
| `/api/v1/agent/yearly-commission/settle` | POST | agent:commission:save | 触发结算（手动/cron） |
| `/api/v1/agent/agents` | GET | agent:list | 列表（可 region_code 过滤） |
| `/api/v1/agent/agents` | POST | agent:save | 创建区域代理 |
| `/api/v1/asset/batches/{id}/generate` | POST | asset:batch:save | 生成卡（含防伪字段） |
| `/api/v1/asset/cards/verify/{code}` | GET | **公开** | 防伪核销（无需登录） |

---

## 七、Phase 2 待办（接 Hyperledger Fabric）

| 项 | 描述 | 工作量 |
|---|---|---|
| Fabric 网络 | Docker Compose（peer + orderer + couchdb） | 2h |
| chaincode `cardregistry` | Go：`registerCard` / `verifyCard` | 3h |
| Python SDK | `fabric-sdk-py` 替换 mock | 2h |
| 链上对账任务 | 每日定时核对 unique_code ↔ 链上 hash | 2h |
| 测试网切换 | verify 接口改为真链上查询 | 1h |

---

**维护**：决策变更时同步更新本文档 + memory/project-mis-decisions.md