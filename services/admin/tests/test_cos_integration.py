"""CosStorage 集成测试（Sprint 1 完成后跑；未配凭据时整个文件 skip）。

⚠️ 必须 2 个 env：
- INTEGRATION=1  # 任意值即可
- COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET / COS_REGION 已配

不带 INTEGRATION env 时整文件 pytest 跳过，不会污染日常测试。

预期用法：
    export INTEGRATION=1
    export COS_REGION=ap-guangzhou
    export COS_BUCKET=qm-wx-1418512491
    export COS_SECRET_ID=<...>
    export COS_SECRET_KEY=<...>
    export STORAGE_BACKEND=cos
    PYTHONPATH=. pytest tests/test_cos_integration.py -v

⚠️ 注意：此测试会创建/删除真实对象。生产 / 共享 bucket 上跑需用独立测试 prefix。
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

# 整文件 skip：无 INTEGRATION 或缺 KEY
pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="需要 INTEGRATION=1 + COS_* 凭据才能跑",
)


@pytest.fixture
def require_cos_env(monkeypatch):
    """确保测试用 cos backend。"""
    monkeypatch.setenv("STORAGE_BACKEND", "cos")
    # 让 settings 重读
    from app.services import storage as pkg

    pkg.reset_storage()
    yield
    pkg.reset_storage()


@pytest.mark.asyncio
async def test_put_get_delete_roundtrip(require_cos_env):
    from app.services.storage import ObjectKey, UploadRequest, get_storage

    storage = get_storage()
    assert storage.__class__.__name__ == "CosStorage", f"未启用 cos backend, actual={storage.__class__.__name__}"

    key = ObjectKey("integration-tests/test-1.txt")
    try:
        result = await storage.put(UploadRequest(key=key, data=b"hello cos", content_type="text/plain"))
        assert result.size == 9
        assert result.etag
        assert result.url.startswith(("http://", "https://"))

        data = await storage.get_bytes(key)
        assert data == b"hello cos"

        meta = await storage.head(key)
        assert meta is not None
        assert meta.size == 9
        assert "text/plain" in (meta.content_type or "")
    finally:
        await storage.delete(key)


@pytest.mark.asyncio
async def test_presigned_upload_url_works(require_cos_env):
    """用 presigned URL 真打一个 PUT，验证 URL + Required Headers 有效。"""
    import httpx

    from app.services.storage import ObjectKey, get_storage

    storage = get_storage()
    key = ObjectKey("integration-tests/presign.txt")
    p = await storage.presigned_upload(
        key,
        content_type="text/plain",
        expires=timedelta(minutes=5),
    )

    # 注：put_object 类型预签名返回给 httpx.put (browser 也能用)
    try:
        resp = httpx.put(p.url, content=b"presign test", headers=dict(p.required_headers), timeout=30)
        assert resp.status_code == 200, f"PUT 失败: {resp.status_code} {resp.text[:200]}"
        # 验证对象已写入
        assert await storage.get_bytes(key) == b"presign test"
    finally:
        await storage.delete(key)


@pytest.mark.asyncio
async def test_presigned_download_returns_valid_url(require_cos_env):
    import httpx

    from app.services.storage import ObjectKey, UploadRequest, get_storage

    storage = get_storage()
    key = ObjectKey("integration-tests/presign-dl.txt")
    try:
        await storage.put(UploadRequest(key=key, data=b"download me", content_type="text/plain"))
        p = await storage.presigned_download(key, expires=timedelta(minutes=5))
        resp = httpx.get(p.url, timeout=30)
        assert resp.status_code == 200
        assert resp.content == b"download me"
    finally:
        await storage.delete(key)


@pytest.mark.asyncio
async def test_list_objects_finds_written(require_cos_env):
    from app.services.storage import ObjectKey, UploadRequest, get_storage

    storage = get_storage()
    keys = [ObjectKey(f"integration-tests/list-{i}.txt") for i in range(3)]
    try:
        for i, k in enumerate(keys):
            await storage.put(UploadRequest(key=k, data=f"x{i}".encode()))
        found = []
        async for meta in storage.list_objects("integration-tests/list-"):
            found.append(str(meta.key))
        assert sorted(found) == sorted(str(k) for k in keys)
    finally:
        for k in keys:
            await storage.delete(k)


@pytest.mark.asyncio
async def test_head_missing_returns_none(require_cos_env):
    from app.services.storage import ObjectKey, get_storage

    storage = get_storage()
    meta = await storage.head(ObjectKey("integration-tests/does-not-exist-xxx.txt"))
    assert meta is None


@pytest.mark.asyncio
async def test_health_returns_cos(require_cos_env):
    from app.services.storage import get_storage

    storage = get_storage()
    h = await storage.health()
    assert h["backend"] == "cos"
    assert h["region"] == os.getenv("COS_REGION")
    assert h["bucket"] == os.getenv("COS_BUCKET")
