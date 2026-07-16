"""部门管理路由测试（flat + CRUD，前端建树）

覆盖 routes/departments.py：
- create / list / update / delete 完整循环
- 删除带子部门的部门被拦截（400）
- 更新不存在的部门 404

权限说明：admin 用户为 super_admin 角色，直通 require_permission；
路由实际要求 system:dept:save（seed 未显式列 api 码，但超管绕过校验）。
"""


def test_department_crud_full_cycle(client, auth_header):
    """create → list 含新部门 → update 改名 → delete → list 不再含。"""
    h = auth_header

    # create
    r = client.post(
        "/admin/api/v1/departments",
        json={"name": "研发中心", "code": "RND", "leader": "张三", "sort": 10},
        headers=h,
    )
    assert r.status_code == 200, r.text
    dept = r.json()
    assert dept["name"] == "研发中心"
    assert dept["code"] == "RND"
    assert dept["leader"] == "张三"
    assert dept["id"] > 0

    # list 含新部门
    lst = client.get("/admin/api/v1/departments", headers=h).json()
    ids = [d["id"] for d in lst["items"]]
    assert dept["id"] in ids

    # update 改名 + 改负责人
    r = client.put(
        f"/admin/api/v1/departments/{dept['id']}",
        json={"name": "技术中心", "code": "TECH", "leader": "李四", "sort": 20, "status": True},
        headers=h,
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["name"] == "技术中心"
    assert updated["leader"] == "李四"

    # delete
    r = client.delete(f"/admin/api/v1/departments/{dept['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    # list 不再含
    lst = client.get("/admin/api/v1/departments", headers=h).json()
    assert dept["id"] not in [d["id"] for d in lst["items"]]


def test_delete_department_with_children_blocked(client, auth_header):
    """父部门下有子部门时，删除父部门返回 400（须先删子部门）。"""
    h = auth_header
    parent = client.post(
        "/admin/api/v1/departments",
        json={"name": "集团总部", "code": "HQ"},
        headers=h,
    ).json()
    child = client.post(
        "/admin/api/v1/departments",
        json={"name": "财务部", "parent_id": parent["id"], "code": "FIN"},
        headers=h,
    ).json()
    assert child["parent_id"] == parent["id"]

    # 删父 → 400（存在子部门）
    r = client.delete(f"/admin/api/v1/departments/{parent['id']}", headers=h)
    assert r.status_code == 400
    assert "子部门" in r.json()["detail"]

    # 先删子再删父 → 成功
    assert client.delete(f"/admin/api/v1/departments/{child['id']}", headers=h).status_code == 200
    assert client.delete(f"/admin/api/v1/departments/{parent['id']}", headers=h).status_code == 200


def test_update_nonexistent_department_404(client, auth_header):
    """PUT 不存在的部门 id → 404。"""
    h = auth_header
    r = client.put(
        "/admin/api/v1/departments/999999",
        json={"name": "不存在", "sort": 0, "status": True},
        headers=h,
    )
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]
