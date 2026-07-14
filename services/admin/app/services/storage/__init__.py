"""Storage 抽象层入口 — 单例工厂 + 测试 reset。

用法：
    from app.services.storage import get_storage
    storage = get_storage()
    await storage.put(UploadRequest(...))

切换后端：设环境变量 STORAGE_BACKEND=cos（Phase 1）+ 配 COS_* 变量。
测试时用 set_storage(LocalStorage(root)) 或 set_storage(MockStorage()) 注入。
"""

from __future__ import annotations

import logging

from ...config import settings
from .errors import (  # re-export
    BackendUnavailable,
    InvalidArgument,
    ObjectNotFound,
    PermissionDenied,
    StorageError,
)
from .local import LocalStorage
from .protocol import (
    ObjectKey,
    ObjectMeta,
    PresignedDownload,
    PresignedUpload,
    Storage,
    UploadRequest,
    UploadResult,
)
from .sts import STSCredential, STSCredentialProvider  # Sprint 1 Phase 2
from .cos import CosStorage  # Sprint 1 —— 顶层 import；SDK import 在 cos.py 内 lazy

__all__ = [
    "ObjectKey",
    "ObjectMeta",
    "PresignedDownload",
    "PresignedUpload",
    "Storage",
    "StorageError",
    "ObjectNotFound",
    "BackendUnavailable",
    "UploadRequest",
    "UploadResult",
    "LocalStorage",
    "get_storage",
    "set_storage",
]


logger = logging.getLogger(__name__)
_storage: Storage | None = None


def get_storage() -> Storage:
    """单例工厂：根据 settings.storage_backend 返回对应实现。

    - 'local' → LocalStorage（默认，dev 用）
    - 'cos' → CosStorage（Phase 1 实装，需 SecretId/SecretKey 已配）
    """
    global _storage
    if _storage is None:
        backend = (settings.storage_backend or "local").lower()
        if backend == "local":
            _storage = LocalStorage(root_dir=settings.storage_local_root or "storage/uploads")
            logger.info("Storage 初始化: local backend, root=%s", settings.storage_local_root)
        elif backend == "cos":
            # Sprint 1：实装 CosStorage，需 settings.cos_secret_id/secret_key/bucket/region
            if not (settings.cos_region and settings.cos_secret_id and settings.cos_secret_key and settings.cos_bucket):
                raise BackendUnavailable(
                    "STORAGE_BACKEND=cos 但 settings.cos_* 凭据不完整；"
                    "需在 .env 设置 COS_REGION/SECRET_ID/SECRET_KEY/BUCKET"
                )
            _storage = CosStorage(
                region=settings.cos_region,
                secret_id=settings.cos_secret_id,
                secret_key=settings.cos_secret_key,
                bucket=settings.cos_bucket,
                scheme=settings.cos_scheme or "https",
            )
            logger.info("Storage 初始化: cos backend, region=%s, bucket=%s",
                        settings.cos_region, settings.cos_bucket)
        else:
            raise BackendUnavailable(f"未知 STORAGE_BACKEND: {backend}")
    return _storage


def set_storage(s: Storage | None) -> None:
    """测试 / 灰度切换入口。设 None 恢复默认单例行为。"""
    global _storage
    _storage = s


def reset_storage() -> None:
    """清空单例，下次 get_storage() 重读 settings。"""
    set_storage(None)
