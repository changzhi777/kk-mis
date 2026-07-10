"""认证安全：JWT + 密码哈希

直接使用 bcrypt 库（避免 passlib 1.7.4 与 bcrypt 4+ 的兼容问题）。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from .config import settings


def hash_password(password: str) -> str:
    """bcrypt 哈希（返回 utf-8 字符串便于存储）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码（bcrypt 限制 72 字节，超长截断前 72 字节）"""
    try:
        pwd = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.access_token_expire)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_token_expire)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
