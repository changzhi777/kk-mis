"""FastAPI 依赖：认证 + 权限校验"""
from typing import List

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Agent, Permission, Role, User, role_permissions, user_roles
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """解析 JWT，返回当前用户"""
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="未认证")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    user = await session.get(User, int(payload["sub"]))
    if not user or not user.status:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


async def get_user_permissions(user_id: int, session: AsyncSession) -> List[str]:
    """查询用户的权限码集合（通过角色聚合）。Redis 缓存（TTL 600s + 主动失效）。"""
    from . import cache
    cache_key = f"user:{user_id}:perms"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return cached
    stmt = (
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .join(Role, Role.id == role_permissions.c.role_id)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user_id)
    )
    result = await session.execute(stmt)
    # scalars().all() 已是标量(code 字符串)，直接去重，勿再取 r[0]（会变首字符）
    codes = list(set(result.scalars().all()))
    await cache.set_json(cache_key, codes)
    return codes


async def get_user_role_codes(user_id: int, session: AsyncSession) -> List[str]:
    """查询用户的角色 code 列表（user_roles → Role.code）。

    **不走 Redis 缓存**：角色变更是低频高危操作（影响 super_admin 判定等安全路径），
    走缓存需联动改 cache.invalidate_user（目前只清 perms/menus）；为保证角色绑定/
    解绑后立即生效，这里每次直查 DB（一次轻量 join，require_permission 高频路径已由
    perms 缓存兜底，影响可控）。
    """
    stmt = (
        select(Role.code)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def is_super_admin(
    user: User,
    session: AsyncSession,
    *,
    role_codes: List[str] | None = None,
) -> bool:
    """判断用户是否拥有 super_admin 角色（替代历史硬编码 username == 'admin'）。

    RBAC 真实来源是 user_roles → Role.code；username 判断不可靠（用户改名/多超管/
    seed 用户名调整等场景会漏判）。调用方若已查过 role_codes 可直传避免重复查询。
    """
    if role_codes is None:
        role_codes = await get_user_role_codes(user.id, session)
    return "super_admin" in role_codes


def require_permission(code: str):
    """权限校验依赖工厂：require_permission('system:user:add')"""
    async def checker(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        # 超管（super_admin 角色）直通：不再硬编码 username == 'admin'
        if await is_super_admin(user, session):
            return user
        codes = await get_user_permissions(user.id, session)
        if code not in codes:
            raise HTTPException(status_code=403, detail=f"无权限: {code}")
        return user

    return checker


async def get_user_scope(
    user: User, session: AsyncSession
) -> tuple[str, list[int]]:
    """返回 (data_scope, agent_ids) 用于 agent 模块数据范围过滤。

    - data_scope: 用户角色的最宽（任一角色 all → "all"，否则 "self"）
    - agent_ids: data_scope="self" 时，user 对应的 Agent 记录 id 列表（用于过滤）
    - super_admin 角色直通 "all"（同 require_permission 逻辑）

    供 agent 模块 list/summary/操作端点做 data_scope=self 数据隔离（2026-07-13）。
    """
    if await is_super_admin(user, session):
        return "all", []
    scopes = (
        await session.execute(
            select(Role.data_scope)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user.id)
        )
    ).scalars().all()
    if any(s == "all" for s in scopes):
        return "all", []
    agent_ids = (
        await session.execute(select(Agent.id).where(Agent.user_id == user.id))
    ).scalars().all()
    return "self", list(agent_ids)
