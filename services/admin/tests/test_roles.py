"""角色管理路由测试（routes/roles.py）

覆盖：list / create / update / delete + 权限绑定/解绑（通过 permission_ids）。
admin 用户属 super_admin 角色，自动通过 system:role:save 权限校验。
"""
import uuid


def test_list_roles_returns_seeded(client, auth_header):
    """GET /roles 返回 seed 的 super_admin / staff 等角色，且每项含 permission_ids 字段。"""
    r = client.get("/admin/api/v1/roles", headers=auth_header)
    assert r.status_code == 200
    items = r.json()["items"]
    codes = {it["code"] for it in items}
    assert "super_admin" in codes
    assert "staff" in codes
    # 每项必须带 permission_ids（即便为空）
    for it in items:
        assert "permission_ids" in it
        assert isinstance(it["permission_ids"], list)
    # super_admin 绑了全部权限，不应为空
    sa = next(it for it in items if it["code"] == "super_admin")
    assert len(sa["permission_ids"]) > 0


def test_create_role_with_permissions(client, auth_header):
    """POST /roles 建角色并绑定 permission_ids；返回 RoleOut（无 permission_ids 字段）。"""
    # 先取一批现有权限 id
    perms = client.get("/admin/api/v1/permissions/flat", headers=auth_header).json()["items"]
    assert len(perms) >= 2
    pid_a, pid_b = perms[0]["id"], perms[1]["id"]

    code = f"test_role_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/admin/api/v1/roles",
        json={
            "code": code,
            "name": "测试角色",
            "sort": 50,
            "status": True,
            "data_scope": "self",
            "remark": "单测创建",
            "permission_ids": [pid_a, pid_b],
        },
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == code
    assert body["name"] == "测试角色"
    assert body["data_scope"] == "self"
    role_id = body["id"]

    # 从 list 验证权限确实绑上了
    items = client.get("/admin/api/v1/roles", headers=auth_header).json()["items"]
    created = next(it for it in items if it["id"] == role_id)
    assert set(created["permission_ids"]) == {pid_a, pid_b}


def test_create_duplicate_role_code_fails(client, auth_header):
    """重复角色编码 → 400。"""
    code = f"dup_{uuid.uuid4().hex[:8]}"
    payload = {"code": code, "name": "第一次", "sort": 0, "status": True,
               "data_scope": "all", "remark": None, "permission_ids": []}
    r1 = client.post("/admin/api/v1/roles", json=payload, headers=auth_header)
    assert r1.status_code == 200

    payload["name"] = "第二次"
    r2 = client.post("/admin/api/v1/roles", json=payload, headers=auth_header)
    assert r2.status_code == 400
    assert "已存在" in r2.json()["detail"]


def test_update_role_rebinds_permissions(client, auth_header):
    """PUT /roles/{id} 更新角色字段 + 重建权限关联（先删后插）。"""
    perms = client.get("/admin/api/v1/permissions/flat", headers=auth_header).json()["items"]
    assert len(perms) >= 3
    pid_a, pid_b, pid_c = perms[0]["id"], perms[1]["id"], perms[2]["id"]

    code = f"upd_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/admin/api/v1/roles",
        json={"code": code, "name": "原", "sort": 0, "status": True,
              "data_scope": "all", "remark": None, "permission_ids": [pid_a]},
        headers=auth_header,
    ).json()
    role_id = created["id"]

    # 改名 + 改 data_scope + 换绑权限 [a] → [b, c]
    r = client.put(
        f"/admin/api/v1/roles/{role_id}",
        json={"code": code, "name": "改后", "sort": 10, "status": True,
              "data_scope": "dept", "remark": "更新", "permission_ids": [pid_b, pid_c]},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "改后"
    assert r.json()["data_scope"] == "dept"

    # 从 list 验证权限确实换了
    items = client.get("/admin/api/v1/roles", headers=auth_header).json()["items"]
    updated = next(it for it in items if it["id"] == role_id)
    assert set(updated["permission_ids"]) == {pid_b, pid_c}
    assert pid_a not in updated["permission_ids"]


def test_update_role_clears_permissions(client, auth_header):
    """PUT 传空 permission_ids → 解绑全部权限。"""
    perms = client.get("/admin/api/v1/permissions/flat", headers=auth_header).json()["items"]
    pid_a = perms[0]["id"]

    code = f"clr_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/admin/api/v1/roles",
        json={"code": code, "name": "清权限", "sort": 0, "status": True,
              "data_scope": "all", "remark": None, "permission_ids": [pid_a]},
        headers=auth_header,
    ).json()
    role_id = created["id"]

    r = client.put(
        f"/admin/api/v1/roles/{role_id}",
        json={"code": code, "name": "清权限", "sort": 0, "status": True,
              "data_scope": "all", "remark": None, "permission_ids": []},
        headers=auth_header,
    )
    assert r.status_code == 200

    items = client.get("/admin/api/v1/roles", headers=auth_header).json()["items"]
    updated = next(it for it in items if it["id"] == role_id)
    assert updated["permission_ids"] == []


def test_delete_role(client, auth_header):
    """DELETE /roles/{id} 删普通角色成功。"""
    code = f"del_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/admin/api/v1/roles",
        json={"code": code, "name": "待删", "sort": 0, "status": True,
              "data_scope": "all", "remark": None, "permission_ids": []},
        headers=auth_header,
    ).json()
    role_id = created["id"]

    r = client.delete(f"/admin/api/v1/roles/{role_id}", headers=auth_header)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # 再删一次 → 404
    r2 = client.delete(f"/admin/api/v1/roles/{role_id}", headers=auth_header)
    assert r2.status_code == 404


def test_cannot_delete_super_admin(client, auth_header):
    """DELETE super_admin 角色 → 400（防误删超管）。"""
    items = client.get("/admin/api/v1/roles", headers=auth_header).json()["items"]
    sa = next(it for it in items if it["code"] == "super_admin")
    r = client.delete(f"/admin/api/v1/roles/{sa['id']}", headers=auth_header)
    assert r.status_code == 400
    assert "超级管理员" in r.json()["detail"]
