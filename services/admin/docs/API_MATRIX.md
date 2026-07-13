# admin API 端点矩阵

> **精确接口清单**：113 个端点 / 28 个路由器，基于源码静态扫描（`app/routes/` + `app/schemas/`）。
> 生成时间：2026-07-13 10:58:44（zcf:init-project 深挖 #1）。
> 配套文档：`RBAC_MATRIX.md`（角色-权限映射）、`../CLAUDE.md`（模块总览）、`PRICING.md`（代理报价规则）。

## 基础约定

| 项 | 值 |
|----|----|
| **全局前缀** | `/admin`（`main.py:61` 统一挂载） |
| **子前缀** | `/api/v1/<domain>/...`（各路由器 `APIRouter(prefix=...)` 定义） |
| **完整路径** | `/admin` + 子前缀 + 端点路径 |
| **认证** | JWT Bearer（`Authorization: Bearer <access_token>`），access 2h / refresh 7d |
| **权限依赖** | `require_permission("code")`（校验权限码）/ `get_current_user`（仅登录即可） |
| **公开端点** | 仅 4 个：`auth/login`、`auth/register`、`auth/refresh`、`auth/oauth/*`、`asset/cards/verify/{unique_code}`、`oa-agent/healthz` |
| **错误格式** | `HTTPException(status_code, detail="...")`，标准 FastAPI 错误体 |
| **OpenAPI** | `GET /docs`（开发）/ `GET /redoc` |

> 路径参数用 `{}` 包裹（如 `/{aid}`）；查询参数标 `query`；请求体标模型名；响应标 `response_model`（未声明的标 `JSON`）。

---

## 端点清单（按路由器分组）

### 1. 认证 auth · `/admin/api/v1/auth`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 1 | POST | `/login` | `LoginRequest` | `TokenResponse` | 公开 |
| 2 | POST | `/register` | `RegisterRequest` | `TokenResponse` | 公开（绑定 staff 角色） |
| 3 | POST | `/refresh` | `RefreshRequest` | `TokenResponse` | 公开 |
| 4 | GET | `/me` | — | `UserInfo` | 登录 |
| 5 | PUT | `/password` | `ChangePasswordRequest` | — | 登录 |
| 6 | POST | `/logout` | — | — | 登录（前端清 token） |
| 7 | GET | `/menus` | — | 菜单树 JSON | 登录 |

### 2. OAuth auth-oauth · `/admin/api/v1/auth/oauth`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 8 | GET | `/{provider}/authorize` | — | 302 重定向 | 公开 |
| 9 | GET | `/{provider}/callback` | — | `TokenResponse` | 公开 |

> provider：`github`（代码就绪，凭证待启用 → 当前 503）/ `wechat`（预留）。详见 `app/oauth/`。

### 3. 工作台 dashboard · `/admin/api/v1/dashboard`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 10 | GET | `/` | — | 聚合 JSON（用户/订单/流水/卡券计数） | 登录 |

### 4. 用户 users · `/admin/api/v1/users`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 11 | GET | `/` | query（keyword/status/dept_id/分页） | `list[UserOut]` | `system:user:list` |
| 12 | GET | `/export` | query | CSV | `system:user:list` |
| 13 | POST | `/` | `UserCreate` | `UserOut` | `system:user:save` |
| 14 | PUT | `/{user_id}` | `UserUpdate` | `UserOut` | `system:user:save` |
| 15 | DELETE | `/{user_id}` | — | — | `system:user:remove` |
| 16 | PUT | `/{user_id}/password` | `UserResetPassword` | — | `system:user:save` |

### 5. 角色 roles · `/admin/api/v1/roles`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 17 | GET | `/` | — | `list[RoleOut]` | `system:role:save` |
| 18 | POST | `/` | `RoleCreate` | `RoleOut` | `system:role:save` |
| 19 | PUT | `/{role_id}` | `RoleUpdate` | `RoleOut` | `system:role:save` |
| 20 | DELETE | `/{role_id}` | — | — | `system:role:save` |

### 6. 权限 permissions · `/admin/api/v1/permissions`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 21 | GET | `/tree` | — | `PermissionOut` 树（递归 children） | `system:permission:save` |
| 22 | GET | `/flat` | — | `list[PermissionOut]` | `system:permission:save` |
| 23 | POST | `/` | `PermissionCreate` | `PermissionOut` | `system:permission:save` |
| 24 | PUT | `/{pid}` | `PermissionUpdate` | `PermissionOut` | `system:permission:save` |
| 25 | DELETE | `/{pid}` | — | — | `system:permission:save` |

### 7. 部门 departments · `/admin/api/v1/departments`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 26 | GET | `/` | — | `list[DepartmentOut]`（树形） | `system:dept:save` |
| 27 | POST | `/` | `DepartmentCreate` | `DepartmentOut` | `system:dept:save` |
| 28 | PUT | `/{did}` | `DepartmentUpdate` | `DepartmentOut` | `system:dept:save` |
| 29 | DELETE | `/{did}` | — | — | `system:dept:save` |

### 8. 审计 audit · `/admin/api/v1/audit`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 30 | GET | `/` | query（user_id/分页/时间） | 审计日志列表 | `system:audit:view` |

### 9. 财务-账户 finance/accounts · `/admin/api/v1/finance/accounts`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 31 | GET | `/` | — | `list[AccountOut]` | `finance:account:save` |
| 32 | POST | `/` | `AccountCreate` | `AccountOut` | `finance:account:save` |
| 33 | PUT | `/{aid}` | `AccountUpdate` | `AccountOut` | `finance:account:save` |
| 34 | DELETE | `/{aid}` | — | — | `finance:account:save` |

### 10. 财务-科目 finance/categories · `/admin/api/v1/finance/categories`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 35 | GET | `/` | — | `list[CategoryOut]`（树形） | `finance:category:save` |
| 36 | POST | `/` | `CategoryCreate` | `CategoryOut` | `finance:category:save` |
| 37 | PUT | `/{cid}` | `CategoryUpdate` | `CategoryOut` | `finance:category:save` |
| 38 | DELETE | `/{cid}` | — | — | `finance:category:save` |

### 11. 财务-流水 finance/transactions · `/admin/api/v1/finance/transactions`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 39 | POST | `/` | `TransactionCreate` | `TransactionOut` | `finance:transaction:save` |
| 40 | GET | `/` | query（type/account_id/category_id/日期/分页） | `list[TransactionOut]` | `finance:transaction:save` |
| 41 | GET | `/export` | query | CSV | `finance:transaction:save` |
| 42 | DELETE | `/{tid}` | — | — | `finance:transaction:save` |

### 12. 财务-报表 finance/reports · `/admin/api/v1/finance/reports`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 43 | GET | `/summary` | query（日期范围） | 收支汇总 JSON | `finance:report:view` |
| 44 | GET | `/by-category` | query（日期范围） | 分类报表 JSON | `finance:report:view` |

### 13. 资产-卡券类型 asset/card-types · `/admin/api/v1/asset/card-types`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 45 | GET | `/` | — | `list[CardTypeOut]` | `asset:type:list` |
| 46 | POST | `/` | `CardTypeCreate` | `CardTypeOut` | `asset:type:save` |
| 47 | PUT | `/{tid}` | `CardTypeUpdate` | `CardTypeOut` | `asset:type:save` |
| 48 | DELETE | `/{tid}` | — | — | `asset:type:save` |

### 14. 资产-批次 asset/batches · `/admin/api/v1/asset/batches`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 49 | GET | `/` | — | `list[BatchOut]` | `asset:batch:list` |
| 49b | GET | `/{batch_id}` | — | `BatchOut` | `asset:batch:list`（2026-07-13 新增） |
| 50 | POST | `/` | `BatchCreate` | `BatchOut` | `asset:batch:save` |
| 51 | POST | `/{batch_id}/generate` | `GenerateCardsRequest` | `list[GeneratedCard]`（明文卡号+密码，一次性） | `asset:batch:save` |
| 52 | DELETE | `/{batch_id}` | — | — | `asset:batch:save` |

### 15. 资产-卡券 asset/cards · `/admin/api/v1/asset/cards`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 53 | GET | `/` | query（batch_id/status/分页） | `list[CardOut]` | `asset:card:list` |
| 54 | POST | `/{card_id}/issue` | `IssueRequest` | `CardOut` | `asset:card:save` |
| 55 | POST | `/{card_id}/void` | — | `CardOut` | `asset:card:save` |

### 16. 资产-防伪核销 asset/cards/verify · `/admin/api/v1/asset/cards/verify`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 56 | GET | `/{unique_code}` | — | `CardVerifyOut` | **公开**（扫码直达） |

### 17. 资产-核销 asset/redemptions · `/admin/api/v1/asset/redemptions`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 57 | POST | `/redeem` | `RedemptionRequest` | `RedemptionOut` | 登录 |
| 58 | POST | `/redeem-batch` | `list[RedemptionRequest]` | `list[dict]`（逐条结果） | 登录 |
| 59 | GET | `/` | query（card_id/method/日期/分页） | `list[RedemptionOut]` | 登录 |

### 18. 代理-区域代理 agent/agents · `/admin/api/v1/agent/agents`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 60 | GET | `/` | query（region_code/status/分页） | `list[AgentOut]` | `agent:list` |
| 61 | POST | `/` | `AgentCreate` | `AgentOut` | `agent:save` |
| 62 | PUT | `/{aid}` | `AgentUpdate` | `AgentOut` | `agent:save` |
| 63 | DELETE | `/{aid}` | — | — | `agent:save` |

### 19. 代理-订单 agent/orders · `/admin/api/v1/agent/orders`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 64 | GET | `/quote` | query（agent_id/batch_id/quantity） | 报价 JSON（单价/折扣/总额/返佣） | `agent:order:list` |
| 65 | GET | `/` | query（agent_id/status/分页） | `list[OrderOut]` | `agent:order:list` |
| 66 | POST | `/` | `OrderCreate` | `OrderOut`（自动应用阶梯折扣） | `agent:order:save` |
| 67 | POST | `/{order_id}/pay` | — | `OrderOut` | `agent:order:save` |
| 68 | POST | `/{order_id}/complete` | — | `OrderOut`（触发单次返佣） | `agent:order:save` |

### 20. 代理-单次返佣 agent/commissions · `/admin/api/v1/agent/commissions`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 69 | GET | `/rules` | — | `list[CommissionRuleOut]` | `agent:commission:view` |
| 70 | POST | `/rules` | `CommissionRuleCreate` | `CommissionRuleOut` | `agent:commission:save` |
| 71 | GET | `/records` | query（agent_id/order_id/分页） | `list[CommissionRecordOut]` | `agent:commission:view` |
| 72 | GET | `/summary` | query（agent_id/日期） | 返佣汇总 JSON | `agent:commission:view` |
| 73 | POST | `/settle` | — | — | `agent:commission:save` |

### 21. 代理-年度返佣 agent/yearly-commission · `/admin/api/v1/agent/yearly-commission`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 74 | GET | `/` | query（agent_id/year） | `list[YearlyCommissionRecordOut]` | `agent:commission:view` |
| 75 | POST | `/settle` | query（year/dry_run） | 结算结果 JSON（支持 dry_run 预演） | `agent:commission:save` |

### 22. OA-公告 oa/announcements · `/admin/api/v1/oa/announcements`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 76 | GET | `/` | query（scope/status/分页） | `list[AnnouncementOut]` | 登录 |
| 77 | POST | `/` | `AnnouncementCreate` | `AnnouncementOut` | `oa:announcement:save` |
| 78 | GET | `/{aid}` | — | `AnnouncementOut` | 登录 |
| 79 | POST | `/{aid}/publish` | — | `AnnouncementOut` | `oa:announcement:save` |
| 80 | POST | `/{aid}/archive` | — | `AnnouncementOut` | `oa:announcement:save` |
| 81 | DELETE | `/{aid}` | — | — | `oa:announcement:save` |

### 23. OA-审批 oa/approvals · `/admin/api/v1/oa/approvals`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 82 | GET | `/flows` | — | `list[ApprovalFlowOut]` | `oa:approval:save` |
| 83 | POST | `/flows` | `ApprovalFlowCreate` | `ApprovalFlowOut` | `oa:approval:save` |
| 84 | GET | `/instances/mine` | — | `list[ApprovalInstanceOut]` | 登录 |
| 85 | GET | `/instances/pending` | — | `list[ApprovalInstanceOut]`（待我审批） | 登录 |
| 86 | POST | `/instances/{iid}/approve` | `ApproveRequest` | — | 登录 |
| 87 | POST | `/instances/{iid}/reject` | `ApproveRequest` | — | 登录 |
| 88 | GET | `/instances/{iid}/records` | — | `list[ApprovalRecordOut]` | 登录 |

### 24. OA-请假 oa/leaves · `/admin/api/v1/oa/leaves`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 89 | POST | `/` | `LeaveCreate` | `LeaveOut`（自动建审批实例） | 登录 |
| 90 | GET | `/` | query（status/分页） | `list[LeaveOut]` | 登录 |
| 91 | GET | `/{lid}` | — | `LeaveOut` | 登录 |

### 25. OA-报销 oa/expenses · `/admin/api/v1/oa/expenses`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 92 | POST | `/` | `ExpenseCreate` | `ExpenseOut`（自动建审批实例） | 登录 |
| 93 | GET | `/` | query（status/日期/分页） | `list[ExpenseOut]` | 登录 |
| 94 | GET | `/export` | query | CSV | 登录 |
| 95 | GET | `/{eid}` | — | `ExpenseOut` | 登录 |

### 26. OA-工作汇报 oa/reports · `/admin/api/v1/oa/reports`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 96 | POST | `/` | `ReportCreate` | `ReportOut` | 登录 |
| 97 | GET | `/` | query（type/分页） | `list[ReportOut]`（我的） | 登录 |
| 98 | GET | `/all` | query | `list[ReportOut]`（全部，管理用） | `oa:report:view` |
| 99 | GET | `/{rid}` | — | `ReportOut` | 登录 |
| 100 | PUT | `/{rid}/read` | — | — | `oa:report:view` |

### 27. OA-考勤 oa/attendance · `/admin/api/v1/oa/attendance`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 101 | POST | `/clock-in` | — | `AttendanceOut` | 登录 |
| 102 | POST | `/clock-out` | — | `AttendanceOut` | 登录 |
| 103 | GET | `/today` | — | `AttendanceOut` | 登录 |
| 104 | GET | `/me` | query（日期范围） | `list[AttendanceOut]` | 登录 |
| 105 | GET | `/stats` | query（日期范围） | 考勤统计 JSON | 登录 |
| 106 | GET | `/export` | query | CSV | 登录 |

### 28. OA-Agent 桥接 oa-agent · `/admin/api/v1/oa-agent`

| # | 方法 | 路径 | 请求体 | 响应 | 权限 |
|---|------|------|--------|------|------|
| 107 | GET | `/healthz` | — | JSON（oa-agent 服务状态） | 公开 |
| 108 | POST | `/chat/sync` | Request body（消息+session） | JSON（同步回复） | 登录 |
| 109 | POST | `/chat` | Request body（消息+session） | **SSE stream**（流式回复） | 登录 |
| 110 | GET | `/skills` | — | list（可用技能） | 登录 |
| 111 | GET | `/sessions` | query（分页） | list（会话列表） | 登录 |
| 112 | GET | `/sessions/{session_id}` | — | JSON（会话详情+消息） | 登录 |

> oa-agent 桥接代理的是独立的 `oa-agent` 服务（`github.com/changzhi777/oa-agent`），通过 HTTP 转发；`/chat` 走 Server-Sent Events 流式输出。

---

## Pydantic 模型字段速查

> 约束标注：`pattern=...` 正则、`ge/le` 数值上下限、`min_length/max_length` 长度、`gt=0` 必须 > 0。`Optional` 字段可空。`from_attributes=True` 表示支持 ORM 模式直接转换。

### auth（`schemas/auth.py`）

| 模型 | 字段 |
|------|------|
| `LoginRequest` | `username: str (1-50)` · `password: str (1-128)` |
| `RegisterRequest` | `username: str (3-50, ^[a-zA-Z0-9_]+$)` · `password: str (6-128)` · `name: str (1-50)` · `phone?: str (≤20)` · `email?: str (≤100)` |
| `ChangePasswordRequest` | `old_password: str (≥1)` · `new_password: str (6-128)` |
| `RefreshRequest` | `refresh_token: str` |
| `UserInfo` | `id, username, name?, email?, phone?, dept_id?, status, roles: list[str], permissions: list[str]` |
| `TokenResponse` | `access_token, refresh_token, token_type="bearer", user: UserInfo` |

### enterprise（`schemas/enterprise.py`）

| 模型 | 字段 |
|------|------|
| `DepartmentCreate/Update` | `name: str (≤100)` · `parent_id?: int` · `code?: str (≤50)` · `leader?: str (≤50)` · `sort: int=0` · `status: bool=true` |
| `DepartmentOut` | + `id: int` |
| `RoleCreate/Update` | `code: str (≤50)` · `name: str (≤50)` · `sort: int=0` · `status: bool=true` · `data_scope: str="all"` · `remark?: str (≤200)` · `permission_ids: list[int]=[]` |
| `RoleOut` | + `id: int` |
| `PermissionCreate/Update` | `parent_id?: int` · `name: str (≤50)` · `code: str (≤100)` · `type: str (menu\|api\|button)` · `path?, method?, icon?` · `sort: int=0` · `visible: bool=true` |
| `PermissionOut` | + `id, children: list[PermissionOut]`（递归树） |
| `UserCreate` | `username: str (1-50)` · `password: str (6-128)` · `name?, email?, phone?` · `dept_id?: int` · `role_ids: list[int]=[]` · `status: bool=true` |
| `UserUpdate` | `name?, email?, phone?, dept_id?, role_ids?: list[int], status?`（全可选） |
| `UserOut` | `id, username, name?, email?, phone?, dept_id?, status, role_ids: list[int]` |
| `UserResetPassword` | `password: str (6-128)` |

### finance（`schemas/finance.py`）

| 模型 | 字段 |
|------|------|
| `AccountCreate` | `name: str (≤50)` · `type: str (cash\|bank\|wechat\|alipay\|other)` · `balance: Decimal=0` · `sort: int=0` · `status: bool=true` |
| `AccountUpdate` | `name?, type?, sort?, status?`（全可选） |
| `AccountOut` | + `id, balance` |
| `CategoryCreate/Update` | `parent_id?: int` · `name: str (≤50)` · `type: str (income\|expense)` · `code?: str` · `sort: int=0` · `status: bool=true` |
| `CategoryOut` | + `id, parent_id` |
| `TransactionCreate` | `type: str (income\|expense)` · `amount: Decimal (gt=0)` · `account_id, category_id: int` · `dept_id?: int` · `transaction_date: datetime` · `remark?: str (≤500)` |
| `TransactionOut` | + `id, user_id?, created_at` |

### asset（`schemas/asset.py`）

| 模型 | 字段 |
|------|------|
| `CardTypeCreate/Update` | `name: str (≤50)` · `type: str (vip\|voucher\|exchange\|stored)` · `face_value: Decimal=0` · `valid_days: int=0` · `fields_config?: str` · `status: bool=true` · `remark?: str` |
| `CardTypeOut` | + `id` |
| `BatchCreate` | `type_id: int` · `name: str (≤100)` · `quantity: int (gt=0)` · `valid_until?: datetime` |
| `BatchOut` | `id, type_id, name, quantity, generated, status, valid_until?, created_at` |
| `GenerateCardsRequest` | `quantity: int (gt=0, le=10000)` |
| `GeneratedCard` | `card_no: str, password: str`（一次性明文返回） |
| `CardOut` | `id, batch_id, type_id, card_no, unique_code?, blockchain_tx_hash?, qr_url?, status, face_value, unit_price?, holder_user_id?, issued_at?, used_at?, valid_until?, last_verified_at?, created_at` |
| `CardVerifyOut` | `unique_code, verified: bool, reason?, card_no_prefix?, batch_id?, type_id?, status?, blockchain_tx_hash?, last_verified_at?` |
| `IssueRequest` | `holder_user_id: int` |
| `RedemptionRequest` | `card_no: str` · `password?: str`（self 自助核销需） · `method: str (scan\|manual\|batch\|self, 默认 scan)` · `remark?: str` |
| `RedemptionOut` | `id, card_id, redeemer_id?, method, amount, remark?, created_at` |

### agent（`schemas/agent.py`）

> 决策 #3（2026-07-13）：区域代理 + 双层返佣。`commission_rate` / `rate` 上限 **0.5（50%）**，单一源 `services.pricing.MAX_COMMISSION_RATE`。

| 模型 | 字段 |
|------|------|
| `AgentCreate` | `user_id: int` · `name?: str` · `region_code: str (2-16)` · `region_name?: str (≤64)` · `commission_rate: Decimal (0-0.5)` · `status: bool=true` · `remark?: str` |
| `AgentUpdate` | `name?, region_code? (2-16), region_name? (≤64), commission_rate? (0-0.5), status?, remark?` |
| `AgentOut` | + `id, created_at` |
| `OrderCreate` | `agent_id, batch_id: int` · `quantity: int (gt=0)` · `remark?: str` |
| `OrderOut` | `id, agent_id, batch_id, quantity, unit_price, original_unit_price, discount_tier?, total, status, region_code?, remark?, created_at` |
| `CommissionRuleCreate` | `level: int (1-2)` · `rate: Decimal (0-0.5)` · `status: bool=true`（兼容旧 3 级分销字段） |
| `CommissionRuleOut` | + `id` |
| `CommissionRecordOut` | `id, order_id, agent_id, level?, amount, status, settled_at?, created_at` |
| `YearlyCommissionRuleCreate` | `tier: str (1-16, T1/T2/T3)` · `min_sales: Decimal (≥0)` · `max_sales?: Decimal (≥0, NULL=无限)` · `commission_pct: Decimal (0-0.5)` · `sort: int=0` · `status: bool=true` |
| `YearlyCommissionRuleOut` | + `id, created_at` |
| `YearlyCommissionRecordOut` | `id, agent_id, year, total_sales, tier?, commission_pct, amount, order_count, payout_status, settled_at?, region_code?, created_at` |

### oa（`schemas/oa.py`）

| 模型 | 字段 |
|------|------|
| `AnnouncementCreate` | `title: str (≤200)` · `content: str (≥1)` · `scope: str (all\|dept, 默认 all)` · `dept_id?: int` · `status: str (draft\|published, 默认 draft)` |
| `AnnouncementOut` | + `id, publisher_id?, created_at, published_at?` |
| `ApprovalFlowCreate` | `name: str (≤100)` · `business_type: str (leave\|expense)` · `nodes_config: str`（JSON 字符串） · `status: bool=true` |
| `ApprovalFlowOut` | + `id` |
| `ApprovalInstanceOut` | `id, flow_id, applicant_id, business_type, business_id, status, current_node, created_at` |
| `ApprovalRecordOut` | `id, instance_id, node, approver_id, action, comment?, created_at` |
| `ApproveRequest` | `comment?: str (≤500)` |
| `LeaveCreate` | `type: str (personal\|sick\|annual)` · `start_date, end_date: datetime` · `days: Decimal (gt=0, le=365)` · `reason?: str (≤500)` |
| `LeaveOut` | + `id, user_id, status, instance_id?, created_at` |
| `ExpenseCreate` | `amount: Decimal (gt=0)` · `category: str (travel\|office\|entertainment\|other)` · `expense_date: datetime` · `reason?: str (≤500)` |
| `ExpenseOut` | + `id, user_id, status, instance_id?, created_at` |
| `ReportCreate` | `type: str (daily\|weekly\|monthly)` · `period_start, period_end: datetime` · `content: str (≥1)` · `plan_next?, problems?` |
| `ReportOut` | + `id, user_id, status, created_at` |
| `AttendanceOut` | `id, user_id, date, clock_in?, clock_out?, status, work_hours?: Decimal` |

---

## 权限码汇总（26 个）

> 完整角色-权限映射见 `RBAC_MATRIX.md`。`super_admin` 拥有全部；`staff` 仅 `dashboard` / `meeting*`。

| 域 | 权限码 | 适用端点 |
|----|--------|----------|
| 系统 | `system:user:list` | #11, #12 |
| 系统 | `system:user:save` | #13, #14, #16 |
| 系统 | `system:user:remove` | #15 |
| 系统 | `system:role:save` | #17-20 |
| 系统 | `system:permission:save` | #21-25 |
| 系统 | `system:dept:save` | #26-29 |
| 系统 | `system:audit:view` | #30 |
| 财务 | `finance:account:save` | #31-34 |
| 财务 | `finance:category:save` | #35-38 |
| 财务 | `finance:transaction:save` | #39-42 |
| 财务 | `finance:report:view` | #43-44 |
| 资产 | `asset:type:list` | #45 |
| 资产 | `asset:type:save` | #46-48 |
| 资产 | `asset:batch:list` | #49 |
| 资产 | `asset:batch:save` | #50-52 |
| 资产 | `asset:card:list` | #53 |
| 资产 | `asset:card:save` | #54-55 |
| 代理 | `agent:list` | #60 |
| 代理 | `agent:save` | #61-63 |
| 代理 | `agent:order:list` | #64-65 |
| 代理 | `agent:order:save` | #66-68 |
| 代理 | `agent:commission:view` | #69, #71-72, #74 |
| 代理 | `agent:commission:save` | #70, #73, #75 |
| OA | `oa:announcement:save` | #77, #79-81 |
| OA | `oa:approval:save` | #82-83 |
| OA | `oa:report:view` | #98, #100 |

> 其余端点（dashboard / 审批操作 / 请假 / 报销 / 考勤 / 核销 / oa-agent）仅 `get_current_user`（登录即可）。

---

## 观察与备注

1. **权限粒度不均**：`roles` / `permissions` / `departments` / `finance/accounts` / `finance/categories` 的 GET 查询也用 `:save` 权限（无 `:list`/`:view` 区分）。`users` / `asset/card-types` / `asset/batches` / `asset/cards` 则有独立 `:list`。`audit` / `finance/reports` 有 `:view`。这不是 bug（设计为"能改才能看"），但若要开放只读角色需新增权限码。

2. **OA 模块权限较松**：审批 approve/reject、请假/报销 CRUD、考勤、核销仅要求登录（`get_current_user`），靠 `data_scope=self` 在数据层隔离。`announcement` / `approval:save` / `report:view` 是仅有的 OA 细粒度权限。

3. **公开端点共 6 个**（路径无认证）：`auth/login`、`auth/register`、`auth/refresh`、`auth/oauth/{provider}/authorize`、`auth/oauth/{provider}/callback`、`asset/cards/verify/{unique_code}`、`oa-agent/healthz`。其中 `verify` 是防伪核销的扫码入口，**有意公开**。

4. **代理返佣合规硬约束**：`commission_rate` / `rate` / `commission_pct` 全部 `le=MAX_COMMISSION_RATE`（0.5），从 `services.pricing` 单一源导入，防漂移。详见 `docs/PRICING.md`。

5. **`oa-agent` 桥接**：`/chat` 是唯一 SSE 流式端点；`/chat/sync` 同步返回。代理到独立 oa-agent 服务（跨仓库 `changzhi777/oa-agent`）。

6. **导出端点共 5 个 CSV**：`users/export`、`finance/transactions/export`、`oa/expenses/export`、`oa/attendance/export`（均返回 CSV 流）。
