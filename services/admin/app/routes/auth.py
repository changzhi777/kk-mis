"""认证路由：登录/当前用户/刷新token/改密/登出"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user, get_user_permissions
from ..models import Role, User, user_roles
from ..schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
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
    user.last_login = datetime.utcnow()
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
