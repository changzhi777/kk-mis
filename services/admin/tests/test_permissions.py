"""权限管理路由测试（routes/permissions.py）

覆盖：tree（树形）/ flat（扁平）+ create / update / delete。
admin 用户属 super_admin 角色，自动通过 system:permission:save 权限校验。
"""
import uuid


def test_permission_flat_returns_items(client, auth_header):
    """GET /permissions/flat 返回扁平列表，含 seed 的 dashboard / system 等权限。"""
    r = client.get("/admin/api/v1/permissions/flat", headers=auth_header)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    codes = {it["code"] for it in items}
    assert "dashboard" in codes
    assert "system" in codes
    # 每项必备字段
    for it in items:
        assert "id" in it and "code" in it and "type" in it
        assert it["type"] in ("menu", "api", "button")


def test_permission_tree_has_roots_and_children(client, auth_header):
    """GET /permissions/tree 返回树形结构：roots 有 children 嵌套。"""
    r = client.get("/admin/api/v1/permissions/tree", headers=auth_header)
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert len(tree) > 0
    # dashboard 是顶级 root（无 parent_id）
    root_codes = {node["code"] for node in tree}
    assert "dashboard" in root_codes
    # system 节点下应有子节点（system:role 等）
    sys_node = next(n for n in tree if n["code"] == "system")
    assert len(sys_node["children"]) > 0
    child_codes = {c["code"] for c in sys_node["children"]}
    assert "system:role" in child_codes
    # flat 总数 == tree 展开后的节点总数（不丢不重）
    flat = client.get("/admin/api/v1/permissions/flat", headers=auth_header).json()["items"]

    def _count(nodes):
        n = 0
        for node in nodes:
            n += 1
            n += _count(node.get("children", []))
        return n

    assert _count(tree) == len(flat)


def test_create_and_update_permission(client, auth_header):
    """POST 建权限 + PUT 更新；code 唯一。"""
    code = f"test_perm_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/admin/api/v1/permissions",
        json={"parent_id": None, "name": "测试权限", "code": code,
              "type": "button", "path": None, "method": None,
              "icon": None, "sort": 99, "visible": True},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == code
    assert body["type"] == "button"
    pid = body["id"]

    # 重复 code → 400
    r_dup = client.post(
        "/admin/api/v1/permissions",
        json={"parent_id": None, "name": "重复", "code": code,
              "type": "button", "path": None, "method": None,
              "icon": None, "sort": 0, "visible": True},
        headers=auth_header,
    )
    assert r_dup.status_code == 400
    assert "已存在" in r_dup.json()["detail"]

    # PUT 更新
    r_upd = client.put(
        f"/admin/api/v1/permissions/{pid}",
        json={"parent_id": None, "name": "改名后", "code": code,
              "type": "api", "path": "/test", "method": "GET",
              "icon": "Edit", "sort": 50, "visible": False},
        headers=auth_header,
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["name"] == "改名后"
    assert r_upd.json()["type"] == "api"
    assert r_upd.json()["visible"] is False

    # 清理
    client.delete(f"/admin/api/v1/permissions/{pid}", headers=auth_header)


def test_delete_permission_with_children_fails(client, auth_header):
    """DELETE 有子节点的权限 → 400（须先删子节点）。"""
    # 先建父 + 子
    parent_code = f"parent_{uuid.uuid4().hex[:8]}"
    parent = client.post(
        "/admin/api/v1/permissions",
        json={"parent_id": None, "name": "父", "code": parent_code,
              "type": "menu", "path": "/p", "method": None,
              "icon": None, "sort": 0, "visible": True},
        headers=auth_header,
    ).json()
    child = client.post(
        "/admin/api/v1/permissions",
        json={"parent_id": parent["id"], "name": "子", "code": f"{parent_code}:c",
              "type": "api", "path": None, "method": "GET",
              "icon": None, "sort": 0, "visible": True},
        headers=auth_header,
    ).json()

    # 删父 → 400
    r = client.delete(f"/admin/api/v1/permissions/{parent['id']}", headers=auth_header)
    assert r.status_code == 400
    assert "子节点" in r.json()["detail"]

    # 先删子再删父 → 200
    assert client.delete(f"/admin/api/v1/permissions/{child['id']}", headers=auth_header).status_code == 200
    assert client.delete(f"/admin/api/v1/permissions/{parent['id']}", headers=auth_header).status_code == 200
