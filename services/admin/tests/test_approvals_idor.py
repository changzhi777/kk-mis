"""OA 审批 IDOR 防护回归测试（B2：instances/{iid}/records + pending 过滤）。

覆盖 routes/oa/approvals.py 的三处 IDOR 防护：
1. GET /instances/{iid}/records — 非申请人/非当前节点审批人/非超管 → 403
2. GET /instances/pending — 非超管且无 oa:approval:save 权限的用户，
   仅可见"当前节点 approver_id == 自己"的实例（leader 节点放宽见 approval_engine）
3. iid 不存在 → 404（前置短路）

用 2 个非 admin 用户（staff_a 提交单 / staff_b 越权探测）+ admin（超管直通）验证三层可见性。
seed.py 中 leave/expense 流程的节点均为 approver_type=user, approver_id=admin.id，
所以 staff_b 既不是申请人也不是审批人，应被 IDOR 拦截。
"""


def _register(client, username):
    """注册普通员工并返回带 Bearer token 的 headers"""
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": username, "password": "test1234", "name": username},
    )
    assert r.status_code == 200, f"注册 {username} 失败: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _submit_leave(client, headers, *, reason="IDOR 测试"):
    """以指定用户提交请假，返回 instance_id（审批流单节点，审批人=admin）"""
    r = client.post(
        "/admin/api/v1/oa/leaves",
        json={
            "type": "personal",
            "start_date": "2026-09-01T00:00:00",
            "end_date": "2026-09-02T00:00:00",
            "days": 1,
            "reason": reason,
        },
        headers=headers,
    )
    assert r.status_code == 200, f"请假提交失败: {r.text}"
    return r.json()["instance_id"]


def test_non_approver_cannot_read_records(client, auth_header):
    """非申请人/非审批人/非超管 GET /instances/{iid}/records → 403；admin 与申请人可读"""
    staff_a = _register(client, "idor_a")
    staff_b = _register(client, "idor_b")
    iid = _submit_leave(client, staff_a, reason="a 的请假")

    # staff_b（与该实例无关）读 records → 403
    r = client.get(f"/admin/api/v1/oa/approvals/instances/{iid}/records", headers=staff_b)
    assert r.status_code == 403
    assert "无权" in r.json()["detail"]

    # 申请人 staff_a 读自己的 records → 200
    r = client.get(f"/admin/api/v1/oa/approvals/instances/{iid}/records", headers=staff_a)
    assert r.status_code == 200
    # 新实例还没审批记录（pending，未触发 approve/reject）
    assert "items" in r.json()

    # admin（超管直通）读 records → 200
    r = client.get(f"/admin/api/v1/oa/approvals/instances/{iid}/records", headers=auth_header)
    assert r.status_code == 200


def test_records_404_when_instance_missing(client, auth_header):
    """iid 不存在 → 404（先于 IDOR 校验短路）"""
    r = client.get(
        "/admin/api/v1/oa/approvals/instances/999999/records", headers=auth_header
    )
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]


def test_pending_list_filters_non_approvers(client, auth_header):
    """pending 列表：非超管且无 oa:approval:save 的用户，只看到当前节点 approver_id==自己 的实例。

    seed 的 leave 流程节点 approver_type=user, approver_id=admin.id：
    - staff_b 不是该实例审批人 → 不应见到
    - admin 是超管 → 能见到全部 pending
    """
    staff_a = _register(client, "idor_pend_a")
    staff_b = _register(client, "idor_pend_b")
    iid = _submit_leave(client, staff_a, reason="pending 过滤测试")

    # staff_b 不是审批人 → pending 列表不含该实例
    pendings_b = client.get(
        "/admin/api/v1/oa/approvals/instances/pending", headers=staff_b
    ).json()["items"]
    assert not any(p["id"] == iid for p in pendings_b), (
        "staff_b 不应看到他人审批中的实例（IDOR pending 过滤失效）"
    )

    # admin（超管）能看到该 pending 实例
    pendings_admin = client.get(
        "/admin/api/v1/oa/approvals/instances/pending", headers=auth_header
    ).json()["items"]
    assert any(p["id"] == iid for p in pendings_admin), "admin 应能见到全部 pending"
