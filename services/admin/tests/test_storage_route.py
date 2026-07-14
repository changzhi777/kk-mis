"""Storage 路由测试：presign + health（Phase 2）

local backend 下 presign 返 400（不支持直传）；类型/大小校验；auth 守卫。
cos backend 的 presign 真打在 test_cos_integration.py 覆盖（presigned_upload_url_works）。
"""


def test_health_returns_backend(client):
    r = client.get("/admin/api/v1/storage/health")
    assert r.status_code == 200
    assert "backend" in r.json()


def test_presign_local_backend_rejects(client, auth_header):
    """local backend 不支持前端直传 → 400 提示走中转。"""
    r = client.post(
        "/admin/api/v1/storage/presign",
        json={"filename": "a.jpg", "content_type": "image/jpeg", "size": 1024},
        headers=auth_header,
    )
    assert r.status_code == 400
    assert "中转" in r.json()["detail"]


def test_presign_rejects_bad_ext(client, auth_header):
    r = client.post(
        "/admin/api/v1/storage/presign",
        json={"filename": "a.exe", "content_type": "application/octet-stream", "size": 1024},
        headers=auth_header,
    )
    assert r.status_code == 400
    assert "类型" in r.json()["detail"]


def test_presign_rejects_oversize(client, auth_header):
    r = client.post(
        "/admin/api/v1/storage/presign",
        json={"filename": "a.jpg", "content_type": "image/jpeg", "size": 200 * 1024 * 1024},
        headers=auth_header,
    )
    assert r.status_code == 413


def test_presign_requires_auth(client):
    r = client.post(
        "/admin/api/v1/storage/presign",
        json={"filename": "a.jpg", "content_type": "image/jpeg", "size": 1024},
    )
    assert r.status_code in (401, 403)


def test_confirm_missing_returns_404(client, auth_header):
    """confirm 不存在的 key → head None → 404。"""
    r = client.post(
        "/admin/api/v1/cms/media/confirm",
        json={"key": "nonexistent_xyz", "name": "a.jpg", "content_type": "image/jpeg", "size": 10},
        headers=auth_header,
    )
    assert r.status_code == 404


def test_confirm_requires_auth(client):
    r = client.post(
        "/admin/api/v1/cms/media/confirm",
        json={"key": "x", "name": "a.jpg", "content_type": "image/jpeg", "size": 10},
    )
    assert r.status_code in (401, 403)
