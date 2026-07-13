# MIS 系统核心决策（2026-07-12 定案）

> **目的**：让接手人/未来自己知道**为什么这样设计**，不只是**怎么设计**。
>
> 决策基于 2026-07-12 一次拍板（与 `~/.claude/projects/-Users-mac-Documents-Claude-Projects-szdhts-a/memory/project-mis-decisions.md` 同步）。

## 5 项决策汇总

| # | 决策 | 结果 | 影响 |
|---|---|---|---|
| 1 | 技术栈 | **Python FastAPI** | 4 模块代码语言、运维工具链 |
| 2 | 系统定位 | **自用单租户** | 无 tenant_id 隔离 |
| 3 | 代理层级 | **3 级**（企业→一级→二级→客户） | ⚠️ 合规边界（见下） |
| 4 | 支付分账 | **记账统计**（先） | 真实分账走人工 |
| 5 | DB 并发 | **< 100 QPS** | 单 PG + asyncpg 池，预警阈值已定 |

## 决策落地映射（代码位置）

### 决策 #1 — Python FastAPI
- 后端栈：`services/admin/app/`（FastAPI 0.110+ + SQLAlchemy 2.0 async + Pydantic 2.6）
- 与会议纪要栈完全一致（`services/meeting-notes/app/`）
- 4 模块路由：`app/routes/{finance,asset,agent}/`

### 决策 #2 — 自用单租户
- ✅ 数据库无 `tenant_id` 字段
- ✅ JWT 不带 tenant claim
- ✅ RBAC 仅基于 `user → role → permission`，无 tenant 隔离层
- **简化收益**：少写约 30% 代码（中间件 + 查询过滤 + 测试 mock）

### 决策 #3 — 3 级代理（合规边界）
**算法合规**（已实现）：
- ✅ 二级代理必须挂一级（`agents.py:31-35` parent_id 校验）
- ✅ 分润按订单直接计算（`orders.py:_calc_commission` 不按团队业绩）
- ✅ 无"加盟费/入门费"字段（`Agent` 模型）
- ✅ CommissionRecord 关联 `order_id`，无"拉人头奖励"

**硬上限防护**（本次新增，2026-07-12）：
- `schemas/agent.py::MAX_COMMISSION_RATE = Decimal("0.5")`
- `Agent.commission_rate` + `CommissionRule.rate` pydantic `le=0.5`
- 测试覆盖：`test_agent.py::test_commission_rule_rate_capped_at_50_percent` 等 4 个

**为什么是 0.5**：
- 中国《禁止传销条例》：超过 3 级分销 + 团队计酬/全额返利 属传销
- 我们选 3 级（临界），必须避免任何"全额返利"特征
- 50% 是销售提成行业上限（典型 SaaS affiliate 30-40%，线下代理可到 50%）

**降级触发**：
- 监管/工商质询 → 立即降 2 级（`agents.parent_id NULL` 即变 2 级，业务改动小）
- 决策 #3 拍板时已留好降级路径

### 决策 #4 — 记账统计
**当前实现**：
- ✅ 财务流水记录 + 账户余额联动（`transactions.py:32-43`）
- ✅ 代理订单 + CommissionRecord（pending/settled 两态）
- ✅ 财务 `summary` 聚合 API
- ❌ 真实支付分账（**未对接**微信/支付宝）

**触发升级**：
- 代理数 ≥ 100 + 月成交 ≥ 50 万 → 评估对接微信支付服务商分账接口
- 升级前需财务合规 + 资质申请

### 决策 #5 — 低并发（< 100 QPS）
**架构**：
- 单 PostgreSQL 库 + asyncpg 连接池（20-50 连接）
- Redis 仅用于 session/限流（不主用缓存）
- 无 OLAP / ClickHouse / 分库分表

**预警阈值**：
| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 慢查询 | > 200ms 持续 | 加索引 + EXPLAIN |
| 连接池等待 | > 10ms | 调大 pool_size / 优化慢查询 |
| 单表行数 | > 5000 万 | 归档冷数据 / 分区表 |
| 写 QPS | > 500 | 评估读写分离 |

**架构预留**：
- 代码层用 SQLAlchemy session 抽象（`get_session` Depends）
- 加缓存 decorator 预留开关（`@cache_optional(ttl=60)`）
- 未来扩展不重构，只加从库 + Redis 主用

## 4 模块当前状态（2026-07-12 验证）

| 模块 | 后端代码 | 测试 | 前端视图 | 决策落地 |
|---|---|---|---|---|
| 企业管理（users/roles/permissions/departments） | 549 行 | 7 测试 | ✅ | 单租户 ✅ |
| 资产管理（card_types/batches/cards/redemptions） | 434 行 | 4 测试 | ✅ | 低并发 ✅ |
| 代理销售（agents/orders/commissions） | 375 行 | 6 测试（含 4 新增合规防护） | ✅ | 3 级 + 合规防护 ✅ |
| 财务管理（accounts/categories/transactions/reports） | 430 行 | (新增建议) | ✅ | 记账统计 ✅ |

## 后续步骤（按优先级）

1. **法务审查 3 级代理分销计酬规则**（决策 #3 强制前置）
2. **财务模块补测试**（transactions / accounts / categories / reports）
3. **前端 Commission 视图** 展示按层级的分润明细 + 导出
4. **资产模块** 补批次生成 + 核销端到端测试（已有 4 个基础测试）
5. **企业模块** 文档化 RBAC 权限矩阵（已有审计日志，可生成）

## Why

决策文档化的目的是让任何接手人（哪怕不是原作者）能在 5 分钟内理解架构取舍。**决策本身可能过时**——业务规模触发升级时，回来改这份文档即可。

## How to apply

- 新增模块前先看本文件 + memory 决策
- 改 commission_rate 上限必须先讨论（不能擅自）
- 加 tenant_id 是反决策（决策 #2 单租户），必须先改决策
- DB 性能预警触发 → 先看本文件的"预警阈值"再决策是否升级架构

关联：根 CLAUDE.md / services/admin/CLAUDE.md / memory project-mis-decisions.md