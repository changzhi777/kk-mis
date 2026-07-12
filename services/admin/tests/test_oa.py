"""OA 办公关键路径测试：公告发布 + 请假/报销审批 + 工作汇报 + 考勤打卡"""


def test_announcement_publish(client, auth_header):
    """公告：草稿创建 → 发布 → 状态 published"""
    a = client.post(
        "/admin/api/v1/oa/announcements",
        json={"title": "测试公告", "content": "内容", "scope": "all", "status": "draft"},
        headers=auth_header,
    ).json()
    assert a["status"] == "draft"
    r = client.post(f"/admin/api/v1/oa/announcements/{a['id']}/publish", headers=auth_header)
    assert r.json()["status"] == "published"


def test_leave_approval_chain(client, auth_header):
    """请假：提交 → 自动触发审批实例 → approve → 请假状态 approved"""
    h = auth_header
    lr = client.post(
        "/admin/api/v1/oa/leaves",
        json={
            "type": "personal",
            "start_date": "2026-07-20T00:00:00",
            "end_date": "2026-07-21T00:00:00",
            "days": 1.5,
            "reason": "测试请假",
        },
        headers=h,
    ).json()
    assert lr["status"] == "pending"
    iid = lr["instance_id"]
    assert iid is not None
    # 审批通过
    ap = client.post(
        f"/admin/api/v1/oa/approvals/instances/{iid}/approve",
        json={"comment": "同意"},
        headers=h,
    ).json()
    assert ap["status"] == "approved"
    # 请假业务状态由引擎同步
    cur = client.get(f"/admin/api/v1/oa/leaves/{lr['id']}", headers=h).json()
    assert cur["status"] == "approved"


def test_expense_approval_chain(client, auth_header):
    """报销：提交 → 审批 → approved（验证审批引擎对多业务类型通用）"""
    h = auth_header
    er = client.post(
        "/admin/api/v1/oa/expenses",
        json={
            "amount": 500,
            "category": "office",
            "expense_date": "2026-07-12T00:00:00",
            "reason": "办公用品",
        },
        headers=h,
    ).json()
    assert er["status"] == "pending"
    iid = er["instance_id"]
    assert iid is not None
    client.post(
        f"/admin/api/v1/oa/approvals/instances/{iid}/approve",
        json={"comment": "ok"},
        headers=h,
    )
    cur = client.get(f"/admin/api/v1/oa/expenses/{er['id']}", headers=h).json()
    assert cur["status"] == "approved"


def test_report_create_and_read(client, auth_header):
    """工作汇报：创建 → 我的列表 → 标记已读"""
    h = auth_header
    r = client.post(
        "/admin/api/v1/oa/reports",
        json={
            "type": "weekly",
            "period_start": "2026-07-06T00:00:00",
            "period_end": "2026-07-12T23:59:59",
            "content": "本周完成OA测试",
            "plan_next": "下周收尾",
        },
        headers=h,
    ).json()
    assert r["status"] == "submitted"
    # 列表含新建
    items = client.get("/admin/api/v1/oa/reports", headers=h).json()["items"]
    assert any(i["id"] == r["id"] for i in items)
    # 标记已读
    rd = client.put(f"/admin/api/v1/oa/reports/{r['id']}/read", headers=h).json()
    assert rd["status"] == "read"


def test_attendance_clock_flow(client, auth_header):
    """考勤：上班打卡 → 重复拒绝 → 今日状态 → 下班 → 月统计 → 明细"""
    h = auth_header
    ci = client.post("/admin/api/v1/oa/attendance/clock-in", headers=h).json()
    assert ci["clock_in"] is not None
    # 重复上班打卡拒绝
    dup = client.post("/admin/api/v1/oa/attendance/clock-in", headers=h)
    assert dup.status_code == 400
    # 今日状态
    today = client.get("/admin/api/v1/oa/attendance/today", headers=h).json()
    assert today["clock_in"] is not None
    # 下班打卡 + 工时计算
    co = client.post("/admin/api/v1/oa/attendance/clock-out", headers=h).json()
    assert co["clock_out"] is not None
    assert co["work_hours"] is not None
    # 月统计
    stats = client.get("/admin/api/v1/oa/attendance/stats", headers=h).json()
    assert stats["total"] >= 1
    # 月明细
    me = client.get("/admin/api/v1/oa/attendance/me", headers=h).json()["items"]
    assert len(me) >= 1
