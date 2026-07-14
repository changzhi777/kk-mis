"""CMS C 端用户认证（独立 JWT，公开注册/登录）

JWT 复用 JWT_SECRET，payload type=end_user 区分 admin（type=access）。
get_end_user 为可选依赖（未登录返回 None），公开页匿名/登录皆可。
"""
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...db import get_session
from ...models import EndUser
from ...schemas.cms import EndUserLogin, EndUserOut, EndUserRegister
from ...security import hash_password, verify_password

router = APIRouter(prefix="/api/v1/cms/auth", tags=["cms-auth"])

_bearer = HTTPBearer(auto_error=False)


def _make_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "end_user",
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_end_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> EndUser | None:
    """可选依赖：校验 C 端 JWT，未登录/无效返回 None"""
    if not creds or creds.scheme.lower() != "bearer":
        return None
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception:
        return None
    if payload.get("type") != "end_user":
        return None
    return await session.get(EndUser, int(payload["sub"]))


@router.post("/register")
async def register(req: EndUserRegister, session: AsyncSession = Depends(get_session)):
    """C 端注册（手机号 + 密码）"""
    exists = (
        await session.execute(select(EndUser).where(EndUser.phone == req.phone))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "手机号已注册")
    u = EndUser(phone=req.phone, password_hash=hash_password(req.password), nickname=req.nickname)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return {"token": _make_token(u.id), "user": EndUserOut.model_validate(u).model_dump()}


@router.post("/login")
async def login(req: EndUserLogin, session: AsyncSession = Depends(get_session)):
    """C 端登录（手机号 + 密码 → JWT）"""
    u = (
        await session.execute(select(EndUser).where(EndUser.phone == req.phone))
    ).scalar_one_or_none()
    if not u or not verify_password(req.password, u.password_hash):
        raise HTTPException(401, "手机号或密码错误")
    return {"token": _make_token(u.id), "user": EndUserOut.model_validate(u).model_dump()}


@router.get("/me")
async def me(user: EndUser | None = Depends(get_end_user)):
    """当前 C 端用户（需登录）"""
    if not user:
        raise HTTPException(401, "未登录")
    return EndUserOut.model_validate(user).model_dump()
