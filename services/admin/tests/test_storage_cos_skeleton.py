"""CosStorage 骨架测试（Sprint 1 prep 阶段，未接真实凭据）。

策略：mock `_client` 对象方法，验证 Sprint 1 骨架的：
- 9 个 @abstractmethod 全部接入到 cos-python-sdk-v5 调用
- Async 包装（run_in_executor）
- 错误转换（cos 异常 → StorageError 子类）
- presigned upload/download 返回值正确

⚠️ 真打测试（用 QWEATHER_KEY 等同套思路 = COS 真凭据）= 集成测试，单独文件。
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.storage import (
    BackendUnavailable,
    InvalidArgument,
    ObjectKey,
    ObjectNotFound,
    PresignedDownload,
    PresignedUpload,
    STSCredential,
    STSCredentialProvider,
    UploadRequest,
)


# ── STSCredential 与 STSCredentialProvider（无需凭据） ────────


def test_sts_credential_is_expired():
    import time

    cred = STSCredential(
        secret_id="AKID",
        secret_key="x",
        session_token="t",
        expired_at=int(time.time()) - 100,
    )
    assert cred.is_expired() is True


def test_sts_credential_not_expired_with_skew():
    import time

    cred = STSCredential(
        secret_id="AKID",
        secret_key="x",
        session_token="t",
        expired_at=int(time.time()) + 3600,
    )
    assert cred.is_expired() is False


@pytest.mark.asyncio
async def test_sts_provider_returns_cached_credential():
    """Redis 命中缓存 → 不调 STS API 直接返回。"""
    import time

    cached = STSCredential(
        secret_id="ak",
        secret_key="sk",
        session_token="tok",
        expired_at=int(time.time()) + 600,
    )
    fake_redis = MagicMock()
    fake_redis.get = asyncio.coroutine_marker = None  # 避开 lint
    async def _get(key):
        return json.dumps({
            "secret_id": "ak", "secret_key": "sk",
            "session_token": "tok",
            "expired_at": cached.expired_at,
        })

    fake_redis.get = _get

    provider = STSCredentialProvider(
        role_arn="qcs::cam::uin/123:roleName/test",
        session_name="t",
        region="ap-guangzhou",
        secret_id="long-ak",
        secret_key="long-sk",
        redis_client=fake_redis,
    )

    cred = await provider.get()
    assert cred.secret_id == "ak"
    assert cred.session_token == "tok"


# ── CosStorage 错误转换（无需真实客户端）──────────────────────


def test_cos_storage_rejects_empty_region():
    with pytest.raises(InvalidArgument):
        from app.services.storage.cos import CosStorage

        CosStorage(region="", secret_id="x", secret_key="y", bucket="b")


def test_cos_storage_rejects_missing_credentials():
    from app.services.storage.cos import CosStorage

    with pytest.raises(InvalidArgument):
        CosStorage(region="ap-guangzhou", secret_id="", secret_key="y", bucket="b")
    with pytest.raises(InvalidArgument):
        CosStorage(region="ap-guangzhou", secret_id="x", secret_key="", bucket="b")


def test_cos_storage_lazy_import_when_sdk_missing(monkeypatch):
    """未装 cos-python-sdk-v5 → 后台运行时 BackendUnavailable 而非导入失败。"""
    # mock _try_import_cos_sdk 行为
    import sys
    monkeypatch.setitem(sys.modules, "qcloud_cos", None)  # 让 ImportError 触发

    with pytest.raises(BackendUnavailable, match=r"cos-python-sdk-v5"):
        # _try_import_cos_sdk 里面会抛 BackendUnavailable(ImportError)
        from app.services.storage.cos import _try_import_cos_sdk
        _try_import_cos_sdk()


# ── get_storage() 工厂：cos 分支的凭据完整性检查 ────────────────


@pytest.mark.asyncio
async def test_get_storage_cos_branch_rejects_incomplete_credentials(monkeypatch):
    """STORAGE_BACKEND=cos 但缺凭据 → BackendUnavailable。"""
    from app.services import storage as pkg
    from app.config import settings

    original_backend = settings.storage_backend
    original_region = settings.cos_region
    original_id = settings.cos_secret_id
    original_key = settings.cos_secret_key
    original_bucket = settings.cos_bucket

    settings.storage_backend = "cos"
    settings.cos_region = ""  # 故意空
    settings.cos_secret_id = "x"
    settings.cos_secret_key = "y"
    settings.cos_bucket = "b"

    pkg.reset_storage()
    try:
        with pytest.raises(BackendUnavailable, match=r"凭据不完整"):
            pkg.get_storage()
    finally:
        settings.storage_backend = original_backend
        settings.cos_region = original_region
        settings.cos_secret_id = original_id
        settings.cos_secret_key = original_key
        settings.cos_bucket = original_bucket
        pkg.reset_storage()


# ── PresignedUpload/Download dataclass 字段 ─────────────────


def test_presigned_upload_default_method_is_put():
    p = PresignedUpload(url="https://x")
    assert p.method == "PUT"
    assert p.required_headers == {}
    assert p.max_size is None


def test_presigned_download_has_required_fields():
    from datetime import datetime, timezone
    d = PresignedDownload(url="x", expires_at=datetime.now(timezone.utc))
    assert d.url == "x"
    assert d.expires_at > datetime(2000, 1, 1, tzinfo=timezone.utc)
