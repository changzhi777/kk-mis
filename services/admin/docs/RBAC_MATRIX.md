# RBAC 权限矩阵

> admin 后端的角色-权限-资源关系（决策 #2：自用单租户，无 tenant 隔离）。

## 角色

| 角色 code | 名称 | data_scope | 默认用户 | 创建时机 |
|---|---|---|---|---|
| `super_admin` | 超级管理员 | `all` | admin / admin1234 | seed.py 首次启动 |
| `staff` | 普通员工 | `self` | 注册用户 | seed.py 首次启动 + 注册时自动绑定 |

**data_scope 影响**：SQLAlchemy 查询过滤（`self` 只看自己创建的数据，`all` 看全部）。

## 权限码（20 个，按模块分组）

### 工作台 + 会议纪要
| 权限码 | 名称 | 资源 | super_admin | staff |
|---|---|---|---|---|
| `dashboard` | 工作台 | `/dashboard` | ✅ | ✅ |
| `meeting` | 会议菜单 | `/upload` `/list` | ✅ | ✅ |
| `meeting:list` | 会议列表查询 | `/api/v1/meetings` | ✅ | ✅ |

### 系统管理（仅 super_admin）
| 权限码 | 名称 | 资源 |
|---|---|---|
| `system:user:list` | 用户查询 | `/api/v1/users` |
| `system:user:save` | 用户保存 | `/api/v1/users` |
| `system:user:remove` | 用户删除 | `/api/v1/users` |
| `system:role:save` | 角色保存 | `/api/v1/roles` |
| `system:permission:save` | 权限菜单保存 | `/api/v1/permissions` |
| `system:dept:save` | 部门保存 | `/api/v1/departments` |
| `system:audit:view` | 审计查看 | `/api/v1/audit` |

### 财务管理（仅 super_admin）
| 权限码 | 名称 | 资源 |
|---|---|---|
| `finance:transaction:save` | 流水录入 | `/api/v1/finance/transactions` |
| `finance:report:view` | 报表查看 | `/api/v1/finance/reports` |

### 资产管理（仅 super_admin）
| 权限码 | 名称 | 资源 |
|---|---|---|
| `asset:type:list` / `asset:type:save` | 卡券类型 | `/api/v1/asset/card-types` |
| `asset:batch:list` / `asset:batch:save` | 卡券批次 | `/api/v1/asset/batches` |
| `asset:card:list` / `asset:card:save` | 卡券操作 | `/api/v1/asset/cards` |

### 代理销售（仅 super_admin）
| 权限码 | 名称 | 资源 |
|---|---|---|
| `agent:list` / `agent:save` | 代理管理 | `/api/v1/agent/agents` |
| `agent:order:list` / `agent:order:save` | 订单操作 | `/api/v1/agent/orders` |
| `agent:commission:view` / `agent:commission:save` | 分润结算 | `/api/v1/agent/commissions` |

### OA 办公（super_admin + staff）
| 权限码 | 名称 | 资源 | super_admin | staff |
|---|---|---|---|---|
| `oa:announcement:save` | 公告发布 | `/api/v1/oa/announcements` | ✅ | ❌（只读菜单） |
| `oa` | OA 菜单 | `/leave` `/expense` `/approval` `/report` `/attendance` | ✅ | ✅ |
| `oa:leave` | 请假申请 | `/api/v1/oa/leaves` | ✅ | ✅ |
| `oa:expense` | 报销申请 | `/api/v1/oa/expenses` | ✅ | ✅ |
| `oa:report` | 工作汇报 | `/api/v1/oa/reports` | ✅ | ✅ |
| `oa:approval` | 审批中心 | `/api/v1/oa/approvals` | ✅ | ✅ |
| `oa:attendance` | 考勤打卡 | `/api/v1/oa/attendance` | ✅ | ✅ |
| `oa:approval:save` | 审批管理 | `/api/v1/oa/approvals` | ✅ | ❌ |
| `oa:report:view` | 汇报查阅（管理视角） | `/api/v1/oa/reports/all` | ✅ | ❌ |

### oa-agent（独立服务，仅 super_admin）
| 权限码 | 名称 | 资源 |
|---|---|---|
| `oa_agent` | OA Agent 菜单 | `/oa-agent` |

## 默认角色权限表（seed.py）

**super_admin**：全权限（`*` 通配 + 所有 20 个权限码显式绑定）

**staff**（注册用户自动绑定）：
```python
_STAFF_PERM_CODES = [
    "dashboard", "meeting", "meeting:list",
    "oa", "oa:announcement", "oa:leave", "oa:expense",
    "oa:report", "oa:approval", "oa:attendance",
]
```

## 添加新权限的流程

1. **后端**：在 `app/seed.py::_DEFAULT_PERMISSIONS` 加新行（code, name, type, path, icon, parent, sort）
2. **后端**：路由用 `Depends(require_permission("new:perm:code"))`
3. **前端**：`apps/web/src/router/index.ts` 加路由 + `meta.permission: 'new:perm:code'`
4. **前端**：菜单会自动从 `/api/v1/auth/menus` 拉取（动态菜单）
5. **重新 seed**：删 `storage/admin.db` 重启服务（或手动 insert 到 permissions 表）
6. **测试**：在 `tests/test_auth.py` 加权限矩阵测试（每个 role 对每个 perm 的 access 测试）

## 安全审计备忘（来自 project-mis-rbac-audit.md）

- 路由曾有双 `oa/` 前缀 bug（已修复 + 回归测试）
- 权限码曾有首字符截断 bug（已修复 + 回归测试）
- 审批曾有越权 bug（已修复 + 回归测试）

**教训**：admin 单用户测试 ≠ 系统通过，新增 RBAC 特性必须走**多角色端到端权限矩阵测试**。

## Why

权限矩阵写明文档是为了：
1. 新人快速理解谁能干啥（不用读代码猜）
2. 合规审计（RBAC 是金融/医疗/政府系统的强制审计项）
3. RBAC bug 排查的参考（"X 用户访问 Y 接口被拒" → 查矩阵）

## How to apply

- 加新功能：先在矩阵表里加权限码 → 后端路由 → 前端 meta → 测试覆盖
- 改员工权限：直接改 `_STAFF_PERM_CODES` 列表 + 重启 seed
- 排查权限问题：`SELECT * FROM role_permissions WHERE role_id = ?` 看实际绑定

关联：CLAUDE.md / memory project-mis-decisions.md / memory project-mis-rbac-audit.md