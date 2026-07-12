"""初始数据：超管 + 默认菜单权限 + 默认财务科目（幂等）"""
from sqlalchemy import select

from .config import settings
from .models import FinanceCategory, Permission, Role, User, role_permissions, user_roles
from .security import hash_password

# 默认菜单/权限：(code, name, type, path, icon, parent_code, sort)
_DEFAULT_MENUS = [
    # 工作台（首页）
    ("dashboard", "工作台", "menu", "/dashboard", "House", None, 1),
    # 会议纪要（meeting-notes 服务，菜单纳入 admin 统一导航）
    ("meeting", "会议纪要", "menu", None, "Document", None, 5),
    ("meeting:upload", "上传会议", "menu", "/upload", "Upload", "meeting", 10),
    ("meeting:list", "会议列表", "menu", "/list", "List", "meeting", 20),
    # 企业管理
    ("system", "企业管理", "menu", "/system", "Setting", None, 10),
    ("finance", "财务管理", "menu", "/finance", "Wallet", None, 20),
    # 企业管理子菜单
    ("system:user", "用户管理", "menu", "/system/user", "User", "system", 10),
    ("system:role", "角色管理", "menu", "/system/role", "UserFilled", "system", 20),
    ("system:permission", "权限菜单", "menu", "/system/permission", "Key", "system", 30),
    ("system:dept", "部门管理", "menu", "/system/dept", "OfficeBuilding", "system", 40),
    ("system:audit", "审计日志", "menu", "/system/audit", "Document", "system", 50),
    # 财务子菜单
    ("finance:transaction", "收支流水", "menu", "/finance/transaction", "Money", "finance", 10),
    ("finance:account", "账户管理", "menu", "/finance/account", "CreditCard", "finance", 20),
    ("finance:category", "收支科目", "menu", "/finance/category", "Files", "finance", 30),
    ("finance:report", "统计报表", "menu", "/finance/report", "DataAnalysis", "finance", 40),
    # 关键 api 权限
    ("system:user:list", "用户查询", "api", "/api/v1/users", None, "system:user", 1),
    ("system:user:save", "用户保存", "api", "/api/v1/users", None, "system:user", 2),
    ("system:user:remove", "用户删除", "api", "/api/v1/users", None, "system:user", 3),
    ("system:role:save", "角色保存", "api", "/api/v1/roles", None, "system:role", 1),
    ("finance:transaction:save", "流水录入", "api", "/api/v1/finance/transactions", None, "finance:transaction", 1),
    ("finance:report:view", "报表查看", "api", "/api/v1/finance/reports", None, "finance:report", 1),
    # 资产管理菜单
    ("asset", "资产管理", "menu", "/asset", "Ticket", None, 30),
    ("asset:type", "卡券类型", "menu", "/asset/type", "Files", "asset", 10),
    ("asset:batch", "卡券批次", "menu", "/asset/batch", "Box", "asset", 20),
    ("asset:card", "卡券列表", "menu", "/asset/card", "CreditCard", "asset", 30),
    ("asset:redemption", "核销", "menu", "/asset/redemption", "CircleCheck", "asset", 40),
    # 代理销售菜单
    ("agent", "代理销售", "menu", "/agent", "Connection", None, 40),
    ("agent:agent", "代理管理", "menu", "/agent/agent", "UserFilled", "agent", 10),
    ("agent:order", "订单管理", "menu", "/agent/order", "ShoppingCart", "agent", 20),
    ("agent:commission", "分润报表", "menu", "/agent/commission", "Money", "agent", 30),
    # 资产/代理 api 权限
    ("asset:type:list", "类型查询", "api", "/api/v1/asset/card-types", None, "asset:type", 1),
    ("asset:type:save", "类型保存", "api", "/api/v1/asset/card-types", None, "asset:type", 2),
    ("asset:batch:list", "批次查询", "api", "/api/v1/asset/batches", None, "asset:batch", 1),
    ("asset:batch:save", "批次保存", "api", "/api/v1/asset/batches", None, "asset:batch", 2),
    ("asset:card:list", "卡券查询", "api", "/api/v1/asset/cards", None, "asset:card", 1),
    ("asset:card:save", "卡券操作", "api", "/api/v1/asset/cards", None, "asset:card", 2),
    ("agent:list", "代理查询", "api", "/api/v1/agent/agents", None, "agent:agent", 1),
    ("agent:save", "代理保存", "api", "/api/v1/agent/agents", None, "agent:agent", 2),
    ("agent:order:list", "订单查询", "api", "/api/v1/agent/orders", None, "agent:order", 1),
    ("agent:order:save", "订单操作", "api", "/api/v1/agent/orders", None, "agent:order", 2),
    ("agent:commission:view", "分润查看", "api", "/api/v1/agent/commissions", None, "agent:commission", 1),
    ("agent:commission:save", "分润结算", "api", "/api/v1/agent/commissions", None, "agent:commission", 2),
    # 办公应用（OA）
    ("oa", "办公应用", "menu", None, "Briefcase", None, 50),
    ("oa:announcement", "公告管理", "menu", "/announcement", "Bell", "oa", 10),
    ("oa:announcement:save", "公告发布", "api", "/api/v1/oa/announcements", None, "oa:announcement", 1),
    ("oa:leave", "请假申请", "menu", "/leave", "Calendar", "oa", 20),
    ("oa:expense", "报销申请", "menu", "/expense", "Money", "oa", 25),
    ("oa:approval", "审批中心", "menu", "/approval", "Stamp", "oa", 30),
    ("oa:approval:save", "审批管理", "api", "/api/v1/oa/approvals", None, "oa:approval", 1),
    ("oa:report", "工作汇报", "menu", "/report", "Edit", "oa", 28),
    ("oa:report:view", "汇报查阅", "api", "/api/v1/oa/reports", None, "oa:report", 1),
    ("oa:attendance", "考勤打卡", "menu", "/attendance", "Clock", "oa", 35),
    # 审计 api
    ("system:audit:view", "审计查看", "api", "/api/v1/audit", None, "system:audit", 1),
]

_DEFAULT_CATEGORIES = [
    ("income", "营业收入", "income_revenue"),
    ("income", "其他收入", "income_other"),
    ("expense", "人力成本", "expense_hr"),
    ("expense", "办公费用", "expense_office"),
    ("expense", "差旅费用", "expense_travel"),
    ("expense", "其他支出", "expense_other"),
]

# 普通员工角色（注册用户默认）可见的菜单权限码
_STAFF_PERM_CODES = [
    "dashboard", "meeting", "meeting:list",
    "oa", "oa:announcement", "oa:leave", "oa:expense",
    "oa:report", "oa:approval", "oa:attendance",
]


async def seed_initial_data():
    """幂等写入初始数据（已存在则跳过）"""
    from .db import SessionLocal

    changed = False
    async with SessionLocal() as s:
        # 1. 超管用户
        admin = (
            await s.execute(select(User).where(User.username == settings.init_admin_username))
        ).scalar_one_or_none()
        if not admin:
            admin = User(
                username=settings.init_admin_username,
                password_hash=hash_password(settings.init_admin_password),
                name="超级管理员",
                status=True,
            )
            s.add(admin)
            await s.flush()
            changed = True

        # 2. 超管角色 + 关联
        role = (
            await s.execute(select(Role).where(Role.code == "super_admin"))
        ).scalar_one_or_none()
        if not role:
            role = Role(code="super_admin", name="超级管理员", data_scope="all", status=True, sort=0)
            s.add(role)
            await s.flush()
            changed = True
        linked = (
            await s.execute(
                select(user_roles).where(
                    (user_roles.c.user_id == admin.id) & (user_roles.c.role_id == role.id)
                )
            )
        ).first()
        if not linked:
            await s.execute(user_roles.insert().values(user_id=admin.id, role_id=role.id))
            changed = True

        # 3. 默认菜单权限（按 parent_code 顺序建，保证父先于子）
        code_to_id = {}
        for row in (
            await s.execute(select(Permission.code, Permission.id))
        ).all():
            code_to_id[row[0]] = row[1]
        for code, name, ptype, path, icon, parent_code, sort in _DEFAULT_MENUS:
            if code in code_to_id:
                continue
            parent_id = code_to_id.get(parent_code) if parent_code else None
            p = Permission(
                name=name, code=code, type=ptype, path=path, icon=icon,
                parent_id=parent_id, sort=sort, visible=True,
            )
            s.add(p)
            await s.flush()
            code_to_id[code] = p.id
            changed = True

        # 默认请假审批流程（单节点：管理员审批）
        import json as _json
        from .models import ApprovalFlow
        if not (
            await s.execute(select(ApprovalFlow).where(ApprovalFlow.business_type == "leave"))
        ).scalar_one_or_none():
            s.add(ApprovalFlow(
                name="请假审批流程", business_type="leave",
                nodes_config=_json.dumps([{"node": 1, "name": "管理员审批", "approver_type": "user", "approver_id": 1}]),
                status=True,
            ))
            changed = True
        # 默认报销审批流程
        if not (
            await s.execute(select(ApprovalFlow).where(ApprovalFlow.business_type == "expense"))
        ).scalar_one_or_none():
            s.add(ApprovalFlow(
                name="报销审批流程", business_type="expense",
                nodes_config=_json.dumps([{"node": 1, "name": "管理员审批", "approver_type": "user", "approver_id": 1}]),
                status=True,
            ))
            changed = True

        # 普通员工角色（注册用户默认绑定，基础菜单权限）
        staff = (
            await s.execute(select(Role).where(Role.code == "staff"))
        ).scalar_one_or_none()
        if not staff:
            staff = Role(code="staff", name="普通员工", data_scope="self", status=True, sort=100)
            s.add(staff)
            await s.flush()
            changed = True
        for code in _STAFF_PERM_CODES:
            pid = code_to_id.get(code)
            if not pid:
                continue
            linked = (
                await s.execute(
                    select(role_permissions).where(
                        (role_permissions.c.role_id == staff.id)
                        & (role_permissions.c.permission_id == pid)
                    )
                )
            ).first()
            if not linked:
                await s.execute(
                    role_permissions.insert().values(role_id=staff.id, permission_id=pid)
                )
                changed = True

        # 4. 默认财务科目
        for ctype, name, code in _DEFAULT_CATEGORIES:
            exists = (
                await s.execute(select(FinanceCategory).where(FinanceCategory.code == code))
            ).scalar_one_or_none()
            if not exists:
                s.add(FinanceCategory(name=name, type=ctype, code=code, status=True, sort=0))
                changed = True

        if changed:
            await s.commit()
