"""工作台聚合路由测试（routes/dashboard.py）

覆盖 GET /api/v1/dashboard：
- 返回结构完整（todos / counts / me / latest_announcements 四大块）
- 个人 OA 概况字段类型正确（month_expense float / report_count int）
- 无 token → 401
"""


def test_dashboard_returns_aggregated_structure(client, auth_header):
    """GET /dashboard 返回四大块聚合结构 + 字段类型正确。"""
    r = client.get("/admin/api/v1/dashboard", headers=auth_header)
    assert r.status_code == 200, r.text
    data = r.json()

    # 四大顶层键
    assert set(["todos", "counts", "me", "latest_announcements"]).issubset(data.keys())

    # todos 是列表，每项含 type/label/count/link
    todos = data["todos"]
    assert isinstance(todos, list)
    assert len(todos) >= 1
    for t in todos:
        assert "type" in t and "label" in t and "count" in t and "link" in t
        assert isinstance(t["count"], int)

    # counts 含 announcements（int）
    assert "announcements" in data["counts"]
    assert isinstance(data["counts"]["announcements"], int)

    # me 个人概况：month_expense 是 float，report_count 是 int
    me = data["me"]
    assert isinstance(me["month_expense"], float)
    assert isinstance(me["report_count"], int)
    # clock_in/clock_out 在未打卡时应为 null（首日 admin 无打卡记录）
    # 不强制 None（其他测试可能已打卡），只校验类型合规
    if me["clock_in"] is not None:
        assert isinstance(me["clock_in"], str)

    # latest_announcements 是列表（可能空）
    assert isinstance(data["latest_announcements"], list)


def test_dashboard_requires_auth(client):
    """无 token 访问 /dashboard → 401。"""
    r = client.get("/admin/api/v1/dashboard")
    assert r.status_code == 401
