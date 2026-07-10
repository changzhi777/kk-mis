"""FastAPI 依赖：认证 + 权限校验"""
from typing import List

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Permission, Role, User, role_permissions, user_roles
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
    """查询用户的权限码集合（通过角色聚合）"""
    stmt = (
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .join(Role, Role.id == role_permissions.c.role_id)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user_id)
    )
    result = await session.execute(stmt)
    return list({r[0] for r in result.scalars().all()})


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
