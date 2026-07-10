"""初始数据：超管 + 默认菜单权限 + 默认财务科目（幂等）"""
from sqlalchemy import select

from .config import settings
from .models import FinanceCategory, Permission, Role, User, user_roles
from .security import hash_password

# 默认菜单/权限：(code, name, type, path, icon, parent_code, sort)
_DEFAULT_MENUS = [
    ("system", "企业管理", "menu", "/system", "Setting", None, 10),
    ("finance", "财务管理", "menu", "/finance", "Wallet", None, 20),
    # 企业管理子菜单
    ("system:user", "用户管理", "menu", "/system/user", "User", "system", 10),
    ("system:role", "角色管理", "menu", "/system/role", "UserFilled", "system", 20),
    ("system:permission", "权限菜单", "menu", "/system/permission", "Key", "system", 30),
    ("system:dept", "部门管理", "menu", "/system/dept", "OfficeBuilding", "system", 40),
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
]

_DEFAULT_CATEGORIES = [
    ("income", "营业收入", "income_revenue"),
    ("income", "其他收入", "income_other"),
    ("expense", "人力成本", "expense_hr"),
    ("expense", "办公费用", "expense_office"),
    ("expense", "差旅费用", "expense_travel"),
    ("expense", "其他支出", "expense_other"),
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
