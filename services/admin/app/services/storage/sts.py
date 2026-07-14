"""STS 临时凭证管理（Phase 2 才真用 — Sprint 1 骨架）。

设计：
- 主账号 SecretId/Key 用于调 AssumeRole 拿临时凭证
- 临时凭证写入 Redis 缓存（25min refresh，TTL < 30min expire）
- fail-open：Redis 不可用 → 报错重试或用长连接
- 与 settings.cos_assume_role_arn 配合使用

⚠️ Sprint 1 骨架：仅写类结构，不接入真实 STS（凭据未到）。
Phase 2 用户给 COS_ASSUME_ROLE_ARN 时启用。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .errors import BackendUnavailable

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class STSCredential:
    """临时凭证三件套。"""

    secret_id: str
    secret_key: str
    session_token: str
    expired_at: int  # unix timestamp

    def is_expired(self, skew_seconds: int = 300) -> bool:
        """默认 5min 提前刷新窗口。"""
        return time.time() >= self.expired_at - skew_seconds


class STSCredentialProvider:
    """腾讯云 STS 短期凭证管理 + Redis 缓存。

    用法：
        provider = STSCredentialProvider(
            role_arn='qcs::cam::uin/xxx:roleName/kk-mis-cos-writer',
            session_name='kk-mis',
            duration=1800,
            region='ap-guangzhou',
            secret_id=settings.long_term_secret_id,
            secret_key=settings.long_term_secret_key,
            redis_client=aioredis_client,
        )
        cred = await provider.get()  # 返回 STSCredential（自动 refresh + 缓存）
        config = CosConfig(
            SecretId=cred.secret_id,
            SecretKey=cred.secret_key,
            Token=cred.session_token,
        )
    """

    def __init__(
        self,
        *,
        role_arn: str,
        session_name: str,
        duration: int = 1800,
        region: str,
        secret_id: str,
        secret_key: str,
        redis_client: "Redis | None" = None,
        cache_key_prefix: str = "sts:cos:",
    ) -> None:
        self.role_arn = role_arn
        self.session_name = session_name
        self.duration = duration
        self.region = region
        self.long_term_secret_id = secret_id
        self.long_term_secret_key = secret_key
        self.redis = redis_client
        self.cache_key_prefix = cache_key_prefix

    def _cache_key(self) -> str:
        # 用 role_arn 的一部分做 key（避免 leak 长 SECRET）
        # 例： sts:cos:qcs::cam::uin/10001:roleName/kk-mis-cos-writer
        return f"{self.cache_key_prefix}{self.role_arn}"

    async def get(self) -> STSCredential:
        """取一份有效临时凭证（自动 refresh）。"""
        # 1. 先查 Redis 缓存
        cached = await self._read_cache()
        if cached and not cached.is_expired():
            return cached

        # 2. 缓存没有或过期 → 调 STS AssumeRole
        cred = await self._assume_role()

        # 3. 写回 Redis（fail-open）
        await self._write_cache(cred)
        return cred

    async def _assume_role(self) -> STSCredential:
        """调 tencentcloud-sdk-python AssumeRole。"""
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.sts.v20180813 import sts_client, models
        except ImportError as exc:
            raise BackendUnavailable(
                "tencentcloud-sdk-python 未安装；`pip install tencentcloud-sdk-python`"
            ) from exc

        cred = credential.Credential(self.long_term_secret_id, self.long_term_secret_key)
        http = HttpProfile(endpoint="sts.tencentcloudapi.com")
        profile = ClientProfile(httpProfile=http, signMethod="TC3-HMAC-SHA256")
        client = sts_client.StsClient(cred, self.region, profile)

        req = models.AssumeRoleRequest()
        req.RoleArn = self.role_arn
        req.RoleSessionName = self.session_name
        req.DurationSeconds = self.duration
        # Policy 收紧：限制到当前 bucket 的读写
        # 见 project-cos-research-2026-07-14.md § 4.2
        req.Policy = ""  # Phase 1 默认空，由 settings.sts_policy 注入

        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(None, lambda: client.AssumeRole(req))
        except Exception as exc:
            raise BackendUnavailable(f"STS AssumeRole 失败: {exc}") from exc

        c = resp.Credentials
        return STSCredential(
            secret_id=c.AccessKeyId,
            secret_key=c.SecretAccessKey,
            session_token=c.Token,
            expired_at=int(c.ExpiredTime),
        )

    async def _read_cache(self) -> STSCredential | None:
        if not self.redis:
            return None
        try:
            raw = await self.redis.get(self._cache_key())
            if not raw:
                return None
            data = raw.decode() if isinstance(raw, bytes) else raw
            import json
            j = json.loads(data)
            return STSCredential(**j)
        except Exception as exc:
            logger.warning("STS 缓存读失败: %s", exc)
            return None  # fail-open

    async def _write_cache(self, cred: STSCredential) -> None:
        if not self.redis:
            return
        try:
            ttl = max(60, cred.expired_at - int(time.time()) - 60)  # 留 1min 安全边
            import json
            data = json.dumps({
                "secret_id": cred.secret_id,
                "secret_key": cred.secret_key,
                "session_token": cred.session_token,
                "expired_at": cred.expired_at,
            })
            await self.redis.set(self._cache_key(), data, ex=ttl)
        except Exception as exc:
            logger.warning("STS 缓存写失败: %s", exc)  # fail-open
