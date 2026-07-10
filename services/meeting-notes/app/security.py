"""API 鉴权依赖。

独立模块，避免 main 与 routes 之间的循环导入（SOLID 单一职责）。
"""
import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from .config import settings


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """校验请求头 X-API-Key（时序安全比较，防时序攻击）。

    作为 FastAPI 依赖注入到需要保护的 router / 端点。
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
