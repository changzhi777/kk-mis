"""Storage Protocol 验证测试 — 确保 LocalStorage 符合 Storage 抽象。

策略：用静态 duck-typing + 接口属性 + 测试 get_storage() 工厂逻辑。
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.services import storage as storage_pkg
from app.services.storage import (
    BackendUnavailable,
    LocalStorage,
    ObjectKey,
    Storage,
    get_storage,
    reset_storage,
    set_storage,
)


def test_local_storage_is_storage_instance():
    """LocalStorage 必须是 Storage 子类（duck-typed via abstract base）。"""
    s = LocalStorage(root_dir="/tmp/x")
    assert isinstance(s, Storage)
    # 所有 Storage 方法必须存在
    for name in ("put", "get_bytes", "get_stream", "head", "exists", "delete",
                  "presigned_upload", "presigned_download", "list_objects", "health"):
        assert hasattr(s, name)
        assert callable(getattr(s, name))


def test_object_key_is_hashable():
    """ObjectKey 应当可哈希（dict/set 用）。"""
    k1 = ObjectKey("cms/a.png")
    k2 = ObjectKey("cms/a.png")
    assert hash(k1) == hash(k2)
    assert k1 == k2
    s = {k1}
    assert k2 in s


def test_object_key_is_immutable():
    """ObjectKey 是 frozen dataclass 不能改字段。"""
    k = ObjectKey("cms/a.png")
    with pytest.raises((AttributeError, Exception)):
        k.value = "cms/b.png"  # type: ignore[misc]


def test_domain_types_are_frozen():
    """所有 Domain Types 都是 frozen。"""
    from app.services.storage import (
        ObjectMeta,
        PresignedDownload,
        PresignedUpload,
        UploadRequest,
        UploadResult,
    )
    for cls in (ObjectMeta, PresignedDownload, PresignedUpload, UploadRequest, UploadResult):
        # dataclass(frozen=True) 会设置 __dataclass_params__.frozen = True
        import dataclasses
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} 应为 frozen"


def test_get_storage_default_local(monkeypatch, tmp_path):
    """默认 backend=local → LocalStorage 实例（用 env 注入而非 setattr，避开 Pydantic frozen 行为）。"""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    reset_storage()
    s = get_storage()
    assert isinstance(s, LocalStorage)
    reset_storage()


def test_get_storage_cos_raises(monkeypatch):
    """STORAGE_BACKEND=cos 在 Phase 0 抛 BackendUnavailable（避免误启用）。"""
    # 注意：settings 是 module 单例（from_env() 在 import 时构造），monkeypatch.setenv 不影响
    # 直接修改字段 + reset_storage 触发重读逻辑
    original = settings.storage_backend
    settings.storage_backend = "cos"
    reset_storage()
    try:
        with pytest.raises(BackendUnavailable) as exc_info:
            get_storage()
        assert "cos" in str(exc_info.value).lower() or "尚未实装" in str(exc_info.value)
    finally:
        settings.storage_backend = original
        reset_storage()


def test_set_storage_inject_for_test():
    """set_storage 注入测试用 storage，set None 重置。"""
    fake = LocalStorage(root_dir="/tmp/fake-test-root")
    set_storage(fake)
    assert get_storage() is fake
    reset_storage()
    assert get_storage() is not fake


def test_storage_package_re_exports_errors():
    """StorageError / 子异常都应在 storage 包可导入。"""
    from app.services.storage import BackendUnavailable, ObjectNotFound, StorageError
    assert issubclass(ObjectNotFound, StorageError)
    assert issubclass(BackendUnavailable, StorageError)


# ── ABC 契约 ──────────────────────────────────────────


def test_abc_blocks_incomplete_subclass_at_instantiation():
    """ABC 模式：未实现全部 abstractmethod 的子类在实例化时 TypeError。"""
    class _IncompleteStorage(Storage):  # noqa: F841 — class 定义成功，但实例化报错
        pass

    with pytest.raises(TypeError, match=r"abstract"):
        _IncompleteStorage()


def test_abc_allows_complete_subclass():
    """完整子类可实例化。"""
    from app.services.storage import UploadResult

    class _CompleteStorage(Storage):
        async def put(self, req):
            return UploadResult(key=req.key, url="x", etag="x", size=0)
        async def get_stream(self, key):
            return
            yield b""  # noqa: F471
        async def get_bytes(self, key): return b""
        async def head(self, key): return None
        async def exists(self, key): return False
        async def delete(self, key): return False
        async def presigned_upload(self, key, *, content_type, expires):  # noqa: D401
            from app.services.storage import PresignedUpload
            return PresignedUpload(url="x")
        async def presigned_download(self, key, *, expires):
            from app.services.storage import PresignedDownload
            return PresignedDownload(url="x", expires_at=expires)
        async def list_objects(self, prefix, *, recursive=False):
            return
            yield  # noqa: F471
        async def health(self): return {}

    s = _CompleteStorage()
    assert isinstance(s, Storage)
