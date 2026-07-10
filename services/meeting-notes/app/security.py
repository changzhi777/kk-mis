"""鉴权依赖。

独立模块，避免 main 与 routes 之间的循环导入（SOLID 单一职责）。
支持两种校验：
- verify_jwt：用户登录态（admin 服务签发的 JWT），前端用
- verify_api_key：服务间/脚本（X-API-Key），保留备用
"""
import secrets
from typing import Optional

import jwt
from fastapi import Header, HTTPException, status

from .config import settings


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """校验 X-API-Key（时序安全，服务间/脚本用）"""
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


async def verify_jwt(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """校验 admin 签发的 JWT（用户登录态，前端带 Authorization: Bearer <token>）"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
        )
    return payload
