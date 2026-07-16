"""Redis 缓存层（2026-07-13 引入）。

容错：Redis 不可用时所有操作 fail-open（get 返回 None=miss 走 DB，
set/invalidate 静默失败），缓存层永远不影响请求。

key 约定：
- user:{id}:perms  — 用户权限码 list[str]（require_permission 每请求查，最高频）
- user:{id}:menus  — 用户菜单树 list[dict]（/auth/menus 每刷新拉）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import user_roles

logger = logging.getLogger(__name__)

_client: Optional[Redis] = None
_DEFAULT_TTL = 600  # 10 min（权限/菜单兜底过期）


async def init() -> None:
    """初始化 Redis client（main lifespan startup 调）。失败仅告警不抛（fail-open）。"""
    global _client
    try:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
        await _client.ping()
        logger.info("cache: Redis connected")
    except Exception as e:
        logger.warning("cache: Redis init failed, fail-open mode: %s", e)
        _client = None


async def close() -> None:
    global _client
    if _client:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None


async def get_json(key: str) -> Optional[Any]:
    """取缓存。miss / redis 挂 → None（调用方走 DB）。"""
    if not _client:
        return None
    try:
        raw = await _client.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning("cache.get %s failed: %s", key, e)
        return None


async def set_json(key: str, value: Any, ttl: int = _DEFAULT_TTL) -> None:
    """写缓存。失败静默（不影响主流程）。"""
    if not _client:
        return
    try:
        await _client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.warning("cache.set %s failed: %s", key, e)


async def _delete(*keys: str) -> None:
    if not _client or not keys:
        return
    try:
        await _client.delete(*keys)
    except Exception as e:
        logger.warning("cache.delete failed: %s", e)


async def invalidate_user(user_id: int) -> None:
    """失效某用户的权限 + 菜单缓存（用户改角色时调）。"""
    await _delete(f"user:{user_id}:perms", f"user:{user_id}:menus")


async def invalidate_role(role_id: int, session: AsyncSession) -> None:
    """失效某角色下所有用户的缓存（角色改权限/删角色时调，查 user_roles 批量）。"""
    user_ids = (
        await session.execute(
            select(user_roles.c.user_id).where(user_roles.c.role_id == role_id)
        )
    ).scalars().all()
    for uid in user_ids:
        await invalidate_user(uid)


async def invalidate_all_users() -> None:
    """清所有 user 缓存（权限/菜单表批量变更兜底，scan + delete）。"""
    if not _client:
        return
    try:
        async for key in _client.scan_iter(match="user:*:perms"):
            await _client.delete(key)
        async for key in _client.scan_iter(match="user:*:menus"):
            await _client.delete(key)
    except Exception as e:
        logger.warning("cache.invalidate_all_users failed: %s", e)


async def rate_limit_check(key: str, max_count: int, window_seconds: int = 60) -> bool:
    """固定窗口限流（H16/H17）：返回 True=允许，False=超限。

    - 首次访问 INCR=1 时设置 TTL；
    - Redis 不可用 → fail-open 返回 True（与 cache 模块整体容错策略一致，限流降级不阻塞业务）；
    - 异常 → fail-open 返回 True（限流不应成为单点故障）。

    key 建议格式：`ratelimit:{endpoint}:{ip}`，如 `ratelimit:verify:1.2.3.4`。
    """
    if not _client:
        return True
    try:
        count = await _client.incr(key)
        if count == 1:
            await _client.expire(key, window_seconds)
        return count <= max_count
    except Exception as e:
        logger.warning("cache.rate_limit_check %s failed: %s", key, e)
        return True
