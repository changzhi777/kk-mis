"""认证路由：登录/当前用户/刷新token/改密/登出"""
from ..utils import utcnow
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user, get_user_permissions
from ..models import Permission, Role, User, user_roles
from ..schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _user_info(user: User, session: AsyncSession) -> UserInfo:
    """构造用户信息（含角色码 + 权限码）"""
    role_codes = (
        await session.execute(
            select(Role.code)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user.id)
        )
    ).scalars().all()
    # 超管通配所有权限（前端据 '*' 显示全部菜单）
    if "super_admin" in role_codes:
        perms = ["*"]
    else:
        perms = await get_user_permissions(user.id, session)
    return UserInfo(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        phone=user.phone,
        dept_id=user.dept_id,
        status=user.status,
        roles=list(role_codes),
        permissions=perms,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = (
        await session.execute(select(User).where(User.username == req.username))
    ).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.status:
        raise HTTPException(status_code=403, detail="用户已禁用")
    user.last_login = utcnow()
    await session.commit()
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    info = await _user_info(user, session)
    return TokenResponse(access_token=access, refresh_token=refresh, user=info)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    """自助注册：创建用户并绑定 staff 角色（基础菜单权限），注册即登录"""
    exists = (
        await session.execute(select(User).where(User.username == req.username))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        name=req.name,
        phone=req.phone,
        email=req.email,
        status=True,
    )
    session.add(user)
    await session.flush()
    # 绑定普通员工角色（基础菜单权限）
    staff = (
        await session.execute(select(Role).where(Role.code == "staff"))
    ).scalar_one_or_none()
    if staff:
        await session.execute(user_roles.insert().values(user_id=user.id, role_id=staff.id))
    user.last_login = utcnow()
    await session.commit()
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    info = await _user_info(user, session)
    return TokenResponse(access_token=access, refresh_token=refresh, user=info)


@router.get("/me", response_model=UserInfo)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _user_info(user, session)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, session: AsyncSession = Depends(get_session)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="refresh token 无效")
    user = await session.get(User, int(payload["sub"]))
    if not user or not user.status:
        raise HTTPException(status_code=401, detail="用户无效")
    access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    info = await _user_info(user, session)
    return TokenResponse(access_token=access, refresh_token=new_refresh, user=info)


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(req.new_password)
    await session.commit()
    return {"success": True, "message": "密码已修改"}


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    # JWT 无状态：前端删除 token 即完成登出
    return {"success": True, "message": "已登出"}


@router.get("/menus")
async def my_menus(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """当前用户可见的菜单树（按权限过滤 menu 类型 permission + 祖先补全 + 建树）。Redis 缓存。"""
    from .. import cache
    cached = await cache.get_json(f"user:{user.id}:menus")
    if cached is not None:
        return cached
    all_menus = (
        await session.execute(
            select(Permission)
            .where(Permission.type == "menu", Permission.visible.is_(True))
            .order_by(Permission.sort, Permission.id)
        )
    ).scalars().all()

    # 用户可见的 menu code（super_admin 角色通配 = 全部，2026-07-15 修 username 硬编码）
    role_codes_set = set(
        (
            await session.execute(
                select(Role.code)
                .join(user_roles, user_roles.c.role_id == Role.id)
                .where(user_roles.c.user_id == user.id)
            )
        ).scalars().all()
    )
    visible_codes = None if "super_admin" in role_codes_set else set(
        await get_user_permissions(user.id, session)
    )

    by_id = {m.id: m for m in all_menus}
    visible_ids: set[int] = set()
    for m in all_menus:
        if visible_codes is None or m.code in visible_codes:
            visible_ids.add(m.id)
            # 补全祖先（子有权限 → 父 menu 也显示）
            pid = m.parent_id
            while pid and pid in by_id and pid not in visible_ids:
                visible_ids.add(pid)
                pid = by_id[pid].parent_id

    menus = [m for m in all_menus if m.id in visible_ids]
    nodes = {
        m.id: {
            "id": m.id, "name": m.name, "path": m.path,
            "icon": m.icon, "code": m.code, "children": [],
        }
        for m in menus
    }
    tree = []
    for m in menus:
        node = nodes[m.id]
        if m.parent_id and m.parent_id in nodes:
            nodes[m.parent_id]["children"].append(node)
        else:
            tree.append(node)
    await cache.set_json(f"user:{user.id}:menus", tree)
    return tree


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user)):
    """用户偏好（dashboard 模块顺序等）。"""
    return user.preferences or {}


@router.put("/preferences")
async def update_preferences(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """更新用户偏好（body 合并覆盖）。"""
    user.preferences = {**(user.preferences or {}), **body}
    await session.commit()
    return {"success": True, "preferences": user.preferences}
