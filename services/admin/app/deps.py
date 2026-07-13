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


def require_permission(code: str):
    """权限校验依赖工厂：require_permission('system:user:add')"""
    async def checker(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        # 超管 admin 直通
        if user.username == "admin":
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
    - admin 用户名直通 "all"（同 require_permission 逻辑）

    供 agent 模块 list/summary/操作端点做 data_scope=self 数据隔离（2026-07-13）。
    """
    if user.username == "admin":
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
