"""用户管理路由测试：CRUD + 删除保护 + 缓存失效（B2 cache.invalidate_user 回归）。

依赖 fixture：conftest.py::client（session 级 TestClient）+ auth_header（admin token）。
测试风格与 test_auth.py / test_oa.py 一致：用 TestClient + Bearer token 直打 HTTP。
"""


def test_list_users(client, auth_header):
    """admin 能列出用户，至少含自己"""
    r = client.get("/admin/api/v1/users", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(u["username"] == "admin" for u in data["items"])


def test_list_users_keyword_search(client, auth_header):
    """keyword 过滤生效：搜 admin 能命中"""
    r = client.get("/admin/api/v1/users", params={"keyword": "admin"}, headers=auth_header)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items  # 至少一条
    assert all("admin" in (u["username"] + (u["name"] or "")) for u in items)


def test_create_user_success(client, auth_header):
    """admin 创建用户：返回 UserOut + role_ids 可空"""
    r = client.post(
        "/admin/api/v1/users",
        json={
            "username": "tu_create",
            "password": "test1234",
            "name": "建号测试",
            "email": "tu_create@test.com",
            "phone": "13900000001",
            "role_ids": [],
            "status": True,
        },
        headers=auth_header,
    )
    assert r.status_code == 200
    u = r.json()
    assert u["username"] == "tu_create"
    assert u["id"] > 0
    assert u["role_ids"] == []
    assert u["status"] is True


def test_create_duplicate_username_returns_400(client, auth_header):
    """重复用户名 400（防重复注册）"""
    payload = {"username": "tu_dup", "password": "test1234", "name": "dup1"}
    first = client.post("/admin/api/v1/users", json=payload, headers=auth_header)
    assert first.status_code == 200
    second = client.post("/admin/api/v1/users", json=payload, headers=auth_header)
    assert second.status_code == 400
    assert "已存在" in second.json()["detail"]


def test_update_user_profile(client, auth_header):
    """admin 更新用户 name/email/phone（不动 role_ids 不触发 cache 失效）"""
    # 先建一个
    uid = client.post(
        "/admin/api/v1/users",
        json={"username": "tu_update", "password": "test1234", "name": "原名"},
        headers=auth_header,
    ).json()["id"]
    r = client.put(
        f"/admin/api/v1/users/{uid}",
        json={"name": "改名后", "email": "changed@test.com", "phone": "13800000000"},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "改名后"
    assert body["email"] == "changed@test.com"
    assert body["phone"] == "13800000000"


def test_update_user_role_triggers_cache_invalidation(client, auth_header, monkeypatch):
    """B2 回归：改 role_ids 必须调 cache.invalidate_user，避免旧权限缓存残留。

    staff 角色变更后，require_permission 下一请求会重新从 DB 拉权限码；
    若漏调 invalidate_user，缓存 TTL 600s 内仍是旧权限码 → 越权窗口。
    """
    from app import cache

    called = []

    async def _spy(uid):
        called.append(uid)

    monkeypatch.setattr(cache, "invalidate_user", _spy)

    uid = client.post(
        "/admin/api/v1/users",
        json={"username": "tu_role", "password": "test1234", "name": "换角色"},
        headers=auth_header,
    ).json()["id"]
    # 拿一个真实 role_id（用 staff 角色）
    roles = client.get("/admin/api/v1/roles", headers=auth_header).json()["items"]
    staff_role_id = next(r["id"] for r in roles if r["code"] == "staff")
    # 改 role_ids（非 None → 进入 invalidate 分支）
    r = client.put(
        f"/admin/api/v1/users/{uid}",
        json={"role_ids": [staff_role_id]},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert staff_role_id in r.json()["role_ids"]
    # invalidate_user 必须被调，且入参是当前 user_id
    assert uid in called, "改 role 未触发 cache.invalidate_user，存在权限缓存残留风险"


def test_update_user_without_role_ids_skips_invalidation(client, auth_header, monkeypatch):
    """改 name/email 不应触发 invalidate_user（避免无谓缓存抖动）"""
    from app import cache

    called = []
    monkeypatch.setattr(cache, "invalidate_user", lambda uid: called.append(uid))

    uid = client.post(
        "/admin/api/v1/users",
        json={"username": "tu_norole", "password": "test1234", "name": "只改名"},
        headers=auth_header,
    ).json()["id"]
    client.put(
        f"/admin/api/v1/users/{uid}",
        json={"name": "改名2"},
        headers=auth_header,
    )
    assert called == [], "未改 role 却触发了 invalidate_user"


def test_delete_user_success(client, auth_header):
    """admin 删除普通用户：返回 success，列表不再可见"""
    uid = client.post(
        "/admin/api/v1/users",
        json={"username": "tu_del", "password": "test1234", "name": "待删"},
        headers=auth_header,
    ).json()["id"]
    r = client.delete(f"/admin/api/v1/users/{uid}", headers=auth_header)
    assert r.status_code == 200
    assert r.json()["success"] is True
    # 列表里没了
    items = client.get("/admin/api/v1/users", headers=auth_header).json()["items"]
    assert not any(u["id"] == uid for u in items)


def test_delete_missing_user_returns_404(client, auth_header):
    """删不存在的 user → 404"""
    r = client.delete("/admin/api/v1/users/999999", headers=auth_header)
    assert r.status_code == 404


def test_delete_protected_admin_username(client, auth_header):
    """admin 用户名受保护不可删（防超管锁死系统）"""
    admin_uid = next(
        u["id"] for u in client.get("/admin/api/v1/users", headers=auth_header).json()["items"]
        if u["username"] == "admin"
    )
    r = client.delete(f"/admin/api/v1/users/{admin_uid}", headers=auth_header)
    assert r.status_code == 400
    assert "超级管理员" in r.json()["detail"]


def test_staff_cannot_list_users(client):
    """普通员工无 system:user:list 权限 → 403（防越权枚举用户）"""
    reg = client.post(
        "/admin/api/v1/auth/register",
        json={"username": "tu_staff_block", "password": "test1234", "name": "员工"},
    ).json()
    staff_h = {"Authorization": f"Bearer {reg['access_token']}"}
    r = client.get("/admin/api/v1/users", headers=staff_h)
    assert r.status_code == 403
    assert "system:user:list" in r.json()["detail"]
