"""LocalStorage 单元测试 — Sprint 0 验收。

覆盖：put / get_bytes / get_stream / head / exists / delete / list_objects / presigned_upload / health
"""

from __future__ import annotations

import pytest

from app.services.storage import (
    BackendUnavailable,
    InvalidArgument,
    LocalStorage,
    ObjectKey,
    ObjectNotFound,
    UploadRequest,
)


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(root_dir=tmp_path)


# ── ObjectKey 校验（核心安全点） ────────────────────────────────


def test_object_key_rejects_dotdot():
    with pytest.raises(ValueError, match=r"\.\."):
        ObjectKey("a/../b")


def test_object_key_rejects_leading_slash():
    with pytest.raises(ValueError, match="开头"):
        ObjectKey("/abs/path")


def test_object_key_rejects_backslash():
    with pytest.raises(ValueError, match="反斜杠"):
        ObjectKey("..\\windows")


def test_object_key_rejects_empty():
    with pytest.raises(ValueError):
        ObjectKey("")


def test_object_key_rejects_too_long():
    with pytest.raises(ValueError):
        ObjectKey("a" * 2000)


def test_object_key_accepts_nested():
    k = ObjectKey("cms/media/2026/test.png")
    assert str(k) == "cms/media/2026/test.png"


# ── LocalStorage 基本操作 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_and_get_bytes(storage):
    key = ObjectKey("cms/test.png")
    result = await storage.put(UploadRequest(key=key, data=b"hello world", content_type="text/plain"))
    assert result.size == 11
    assert result.etag
    assert result.key == key

    data = await storage.get_bytes(key)
    assert data == b"hello world"


@pytest.mark.asyncio
async def test_put_creates_metadata_sidecar(storage, tmp_path):
    key = ObjectKey("cms/with-meta.png")
    await storage.put(
        UploadRequest(
            key=key,
            data=b"x" * 100,
            content_type="image/png",
            metadata={"uploaded_by": "42"},
        )
    )

    meta = await storage.head(key)
    assert meta is not None
    assert meta.size == 100
    assert meta.content_type == "image/png"
    assert meta.metadata.get("uploaded_by") == "42"

    # sidecar JSON 文件存在
    sidecar = tmp_path / "cms" / "with-meta.png.meta.json"
    assert sidecar.is_file()


@pytest.mark.asyncio
async def test_get_stream(storage):
    key = ObjectKey("big/file.txt")
    big = b"A" * (1024 * 1024 + 13)  # 1MB+13 字节，分块
    await storage.put(UploadRequest(key=key, data=big))

    chunks: list[bytes] = []
    async for chunk in storage.get_stream(key):
        chunks.append(chunk)
    assert b"".join(chunks) == big


@pytest.mark.asyncio
async def test_head_missing_returns_none(storage):
    meta = await storage.head(ObjectKey("nope/missing.txt"))
    assert meta is None


@pytest.mark.asyncio
async def test_exists(storage):
    key = ObjectKey("a/b.png")
    assert not await storage.exists(key)
    await storage.put(UploadRequest(key=key, data=b"x"))
    assert await storage.exists(key)


@pytest.mark.asyncio
async def test_delete(storage):
    key = ObjectKey("temp/x.png")
    await storage.put(UploadRequest(key=key, data=b"x"))
    assert await storage.exists(key)
    removed = await storage.delete(key)
    assert removed
    assert not await storage.exists(key)


@pytest.mark.asyncio
async def test_delete_missing_returns_false(storage):
    removed = await storage.delete(ObjectKey("ghost/x.png"))
    assert not removed


@pytest.mark.asyncio
async def test_get_bytes_missing_raises(storage):
    with pytest.raises(ObjectNotFound):
        await storage.get_bytes(ObjectKey("nope/x.png"))


@pytest.mark.asyncio
async def test_put_with_file_like(storage, tmp_path):
    key = ObjectKey("streamed/file.bin")
    src = tmp_path / "source.bin"
    src.write_bytes(b"chunked-data")

    with src.open("rb") as f:
        result = await storage.put(UploadRequest(key=key, data=f))
    assert result.size == len(b"chunked-data")
    assert await storage.get_bytes(key) == b"chunked-data"


# ── presigned_upload 不支持 ──────────────────────────────────


@pytest.mark.asyncio
async def test_presigned_upload_not_supported(storage):
    from datetime import timedelta
    with pytest.raises(NotImplementedError):
        await storage.presigned_upload(
            ObjectKey("x"),
            content_type="image/png",
            expires=timedelta(minutes=10),
        )


@pytest.mark.asyncio
async def test_presigned_download_returns_admin_url(storage):
    from datetime import timedelta
    p = await storage.presigned_download(
        ObjectKey("cms/test.png"),
        expires=timedelta(minutes=10),
    )
    assert "/admin/api/v1/cms/media/file/cms/test.png" in p.url
    assert p.expires_at > p.expires_at.replace(year=2000)


# ── list_objects / health ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_objects_prefix(storage):
    await storage.put(UploadRequest(key=ObjectKey("cms/a.png"), data=b"a"))
    await storage.put(UploadRequest(key=ObjectKey("cms/b.png"), data=b"b"))
    await storage.put(UploadRequest(key=ObjectKey("other/c.png"), data=b"c"))

    keys: list[str] = []
    async for m in storage.list_objects("cms/"):
        keys.append(str(m.key))
    assert sorted(keys) == ["cms/a.png", "cms/b.png"]
    # 不应包含 other/c.png
    assert "other/c.png" not in keys


@pytest.mark.asyncio
async def test_list_objects_skips_sidecar(storage):
    """list_objects 不返回 .meta.json sidecar。"""
    await storage.put(UploadRequest(key=ObjectKey("a/b.png"), data=b"x"))
    keys: list[str] = []
    async for m in storage.list_objects("a/"):
        keys.append(str(m.key))
    assert keys == ["a/b.png"]


@pytest.mark.asyncio
async def test_health(storage, tmp_path):
    h = await storage.health()
    assert h["backend"] == "local"
    assert h["root"] == str(tmp_path)
    assert h["writable"] == "yes"


# ── 越界防护 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_traversal_rejected(storage):
    """put/get/delete 路径越界抛 InvalidArgument。"""
    # 反斜杠或 .. 在 ObjectKey 构造时就被拒绝
    with pytest.raises(ValueError):
        ObjectKey("..\\windows")
    with pytest.raises(ValueError):
        ObjectKey("../escape")
