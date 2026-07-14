"""初始数据：超管 + 默认菜单权限 + 默认财务科目 + 默认年度返佣规则（幂等）"""
import json
from decimal import Decimal

from sqlalchemy import select

from .config import settings
from .models import (
    Agent,
    ApprovalFlow,
    FinanceCategory,
    Permission,
    Role,
    User,
    YearlyCommissionRule,
    role_permissions,
    user_roles,
)
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
    # OA Agent（独立 oa-agent 服务入口，2026-07-12 接入）
    ("oa_agent", "OA Agent", "menu", "/oa-agent", "ChatDotRound", None, 60),
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
    ("agent:region", "区域代理", "menu", "/agent/region", "MapLocation", "agent", 10),
    ("agent:order", "订单管理", "menu", "/agent/order", "ShoppingCart", "agent", 20),
    ("agent:commission", "分润报表", "menu", "/agent/commission", "Money", "agent", 30),
    # 资产/代理 api 权限
    ("asset:type:list", "类型查询", "api", "/api/v1/asset/card-types", None, "asset:type", 1),
    ("asset:type:save", "类型保存", "api", "/api/v1/asset/card-types", None, "asset:type", 2),
    ("asset:batch:list", "批次查询", "api", "/api/v1/asset/batches", None, "asset:batch", 1),
    ("asset:batch:save", "批次保存", "api", "/api/v1/asset/batches", None, "asset:batch", 2),
    ("asset:card:list", "卡券查询", "api", "/api/v1/asset/cards", None, "asset:card", 1),
    ("asset:card:save", "卡券操作", "api", "/api/v1/asset/cards", None, "asset:card", 2),
    ("agent:list", "代理查询", "api", "/api/v1/agent/agents", None, "agent:region", 1),
    ("agent:save", "代理保存", "api", "/api/v1/agent/agents", None, "agent:region", 2),
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
    # 内容管理（CMS，2026-07-14 新增：VIP 卡旅游产品介绍页）
    ("cms", "内容管理", "menu", "/cms", "Picture", None, 35),
    ("cms:product", "旅游产品", "menu", "/cms/product", "Tickets", "cms", 10),
    ("cms:media", "素材库", "menu", "/cms/media", "FolderOpened", "cms", 20),
    ("cms:merchant", "合作商户", "menu", "/cms/merchant", "Shop", "cms", 30),
    ("cms:product:list", "产品查询", "api", "/api/v1/cms/products", None, "cms:product", 1),
    ("cms:product:save", "产品保存", "api", "/api/v1/cms/products", None, "cms:product", 2),
    ("cms:media:list", "素材查询", "api", "/api/v1/cms/media", None, "cms:media", 1),
    ("cms:media:upload", "素材上传", "api", "/api/v1/cms/media", None, "cms:media", 2),
    ("cms:merchant:list", "商户查询", "api", "/api/v1/cms/merchants", None, "cms:merchant", 1),
    ("cms:merchant:save", "商户保存", "api", "/api/v1/cms/merchants", None, "cms:merchant", 2),
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

# 业务角色 → 权限码矩阵（2026-07-13 RBAC 重构，5 角色体系）
# super_admin 绑全部权限（见 seed_initial_data，让非 admin 用户名的超管也能过校验）
# staff 用 _STAFF_PERM_CODES（注册默认最小角色）
_ROLE_PERMISSIONS: dict[str, list[str]] = {
    # 行政后勤：会议 + 企业管理(人) + OA 全套
    "ops": [
        "dashboard",
        "meeting", "meeting:upload", "meeting:list",
        "system", "system:user", "system:role", "system:permission", "system:dept", "system:audit",
        "system:user:list", "system:user:save", "system:user:remove", "system:role:save", "system:audit:view",
        "oa", "oa:announcement", "oa:announcement:save", "oa:leave", "oa:expense",
        "oa:approval", "oa:approval:save", "oa:report", "oa:report:view", "oa:attendance",
    ],
    # 财务：财务全套 + 资产看/核销 + 代理返佣结算 + OA 基础
    "finance": [
        "dashboard",
        "finance", "finance:transaction", "finance:account", "finance:category", "finance:report",
        "finance:transaction:save", "finance:report:view",
        "asset", "asset:card", "asset:redemption", "asset:card:list",
        "agent", "agent:commission", "agent:commission:view", "agent:commission:save",
        "oa", "oa:announcement", "oa:leave", "oa:expense", "oa:report", "oa:attendance",
    ],
    # 销售：资产(VIP卡)全套 + 代理区域/订单/分润 + 会议 + OA 基础
    "sales": [
        "dashboard",
        "meeting", "meeting:upload", "meeting:list",
        "asset", "asset:type", "asset:batch", "asset:card", "asset:redemption",
        "asset:type:list", "asset:type:save", "asset:batch:list", "asset:batch:save", "asset:card:list", "asset:card:save",
        "agent", "agent:region", "agent:order", "agent:commission",
        "agent:list", "agent:save", "agent:order:list", "agent:order:save", "agent:commission:view",
        "oa", "oa:announcement", "oa:leave", "oa:expense", "oa:report", "oa:attendance",
    ],
    # 代理商：代理下单/看分润（非管理）+ OA 基础
    "agent": [
        "dashboard",
        "agent", "agent:order", "agent:commission", "agent:order:list", "agent:order:save", "agent:commission:view",
        "oa", "oa:announcement", "oa:leave", "oa:expense", "oa:report", "oa:attendance",
    ],
}

# 业务角色元信息：code → (name, data_scope, sort)
_ROLE_META: dict[str, tuple[str, str, int]] = {
    "ops": ("行政后勤", "all", 10),
    "finance": ("财务", "all", 20),
    "sales": ("销售", "all", 30),
    "agent": ("代理商", "self", 40),
}

# 年度返佣阶梯规则（决策 #3 重构：2026-07-13 区域代理 + 双层返佣）
# (tier, min_sales, max_sales, commission_pct, sort)
_DEFAULT_YEARLY_COMMISSION_RULES = [
    ("T1", Decimal("0"),       Decimal("500000"),  Decimal("0.30"), 1),  # < 50 万 → 30%
    ("T2", Decimal("500000"),  Decimal("2000000"), Decimal("0.40"), 2),  # 50-200 万 → 40%
    ("T3", Decimal("2000000"), None,              Decimal("0.50"), 3),  # > 200 万 → 50%
]

# 默认区域代理（仅 init 时写，admin 可后续编辑）
# (region_code, region_name) — user_id 运行时取 admin.id，避免硬编码 id 漂移
_DEFAULT_REGIONS = [
    ("SH", "上海"),
    ("BJ", "北京"),
    ("GZ", "广州"),
]

# 默认区域代理单次返佣上限（与 services.pricing.MAX_COMMISSION_RATE 对齐）
_DEFAULT_REGION_COMMISSION_RATE = Decimal("0.30")


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

        # 默认请假审批流程（单节点：管理员审批，approver_id 取运行时 admin.id）
        if not (
            await s.execute(select(ApprovalFlow).where(ApprovalFlow.business_type == "leave"))
        ).scalar_one_or_none():
            s.add(ApprovalFlow(
                name="请假审批流程", business_type="leave",
                nodes_config=json.dumps([{"node": 1, "name": "管理员审批", "approver_type": "user", "approver_id": admin.id}]),
                status=True,
            ))
            changed = True
        # 默认报销审批流程
        if not (
            await s.execute(select(ApprovalFlow).where(ApprovalFlow.business_type == "expense"))
        ).scalar_one_or_none():
            s.add(ApprovalFlow(
                name="报销审批流程", business_type="expense",
                nodes_config=json.dumps([{"node": 1, "name": "管理员审批", "approver_type": "user", "approver_id": admin.id}]),
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

        # 业务角色 + 权限绑定（2026-07-13 RBAC 重构，5 角色体系）
        # super_admin 绑全部权限码（让非 admin 用户名的超管也能过权限校验，不再只靠 username 直通）
        # ops/finance/sales/agent 按 _ROLE_PERMISSIONS 矩阵
        all_perm_codes = list(code_to_id.keys())
        role_bind_map: dict[str, list[str]] = {"super_admin": all_perm_codes, **_ROLE_PERMISSIONS}
        for role_code, perm_codes in role_bind_map.items():
            r = (
                await s.execute(select(Role).where(Role.code == role_code))
            ).scalar_one_or_none()
            if not r:
                name, data_scope, sort = _ROLE_META.get(role_code, (role_code, "all", 99))
                r = Role(code=role_code, name=name, data_scope=data_scope, status=True, sort=sort)
                s.add(r)
                await s.flush()
                changed = True
            for code in perm_codes:
                pid = code_to_id.get(code)
                if not pid:
                    continue
                linked = (
                    await s.execute(
                        select(role_permissions).where(
                            (role_permissions.c.role_id == r.id)
                            & (role_permissions.c.permission_id == pid)
                        )
                    )
                ).first()
                if not linked:
                    await s.execute(
                        role_permissions.insert().values(role_id=r.id, permission_id=pid)
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

        # 5. 默认年度返佣阶梯（决策 #3 重构 2026-07-13）
        for tier, min_s, max_s, pct, sort in _DEFAULT_YEARLY_COMMISSION_RULES:
            exists = (
                await s.execute(
                    select(YearlyCommissionRule).where(YearlyCommissionRule.tier == tier)
                )
            ).scalar_one_or_none()
            if not exists:
                s.add(
                    YearlyCommissionRule(
                        tier=tier,
                        min_sales=min_s,
                        max_sales=max_s,
                        commission_pct=pct,
                        sort=sort,
                        status=True,
                    )
                )
                changed = True

        # 6. 默认区域代理（每个区域一个，仅 init 写；user_id 取 admin.id 避免硬编码漂移）
        for region_code, region_name in _DEFAULT_REGIONS:
            exists = (
                await s.execute(
                    select(Agent).where(Agent.region_code == region_code)
                )
            ).scalar_one_or_none()
            if not exists:
                s.add(
                    Agent(
                        user_id=admin.id,
                        name=f"{region_name}代理",
                        region_code=region_code,
                        region_name=region_name,
                        commission_rate=_DEFAULT_REGION_COMMISSION_RATE,
                        status=True,
                    )
                )
                changed = True

        if changed:
            await s.commit()
