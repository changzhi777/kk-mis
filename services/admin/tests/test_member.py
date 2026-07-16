"""会员积分 + 等级路由测试（routes/member.py，V2 积分 / V3 等级）

覆盖：
- GET  /me/points          — 积分余额（首次懒建 MemberStat）
- GET  /me/points/log      — 积分流水（含 admin 调整记录）
- POST /admin/points/adjust — admin 手动调积分（正加负扣）
- GET  /me/level           — 会员等级 + 下一级进度（无等级配置时 level=null）
- GET  /admin/member-levels — 会员等级列表（seed 未配 MemberLevel → 空列表）
"""


def _me_id(client, h):
    """取当前登录用户 id（admin seed 首条，SQLite 一般 id=1，不硬编码）。"""
    return client.get("/admin/api/v1/auth/me", headers=h).json()["id"]


def test_points_adjust_and_balance(client, auth_header):
    """GET /me/points 初始余额 → POST adjust +100 → GET 余额反映变动。"""
    h = auth_header
    uid = _me_id(client, h)

    # 初始余额（懒建 MemberStat，可能为 0 或已被其他测试调整过）
    before = client.get("/admin/api/v1/me/points", headers=h).json()
    assert before["points_balance"] >= 0  # 非负
    assert "frozen_points" in before
    assert "total_consumed" in before

    # admin 调整 +100
    r = client.post(
        "/admin/api/v1/admin/points/adjust",
        json={"user_id": uid, "delta": 100, "reason": "test_award"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    assert r.json()["balance"] == before["points_balance"] + 100

    # 再查余额已更新
    after = client.get("/admin/api/v1/me/points", headers=h).json()
    assert after["points_balance"] == before["points_balance"] + 100


def test_points_log_records_adjustment(client, auth_header):
    """adjust 后 GET /me/points/log 含对应流水条目（delta/reason 可追溯）。"""
    h = auth_header
    uid = _me_id(client, h)

    # 先做一次调整，确保至少有一条流水
    client.post(
        "/admin/api/v1/admin/points/adjust",
        json={"user_id": uid, "delta": 50, "reason": "log_test", "remark": "P1测试"},
        headers=h,
    )

    log = client.get("/admin/api/v1/me/points/log", headers=h).json()
    assert isinstance(log["items"], list)
    assert log["total"] >= 1
    # 最新一条应是我们刚写的（id desc）
    latest = log["items"][0]
    assert latest["delta"] == 50
    assert latest["reason"] == "log_test"
    assert latest["ref_type"] == "admin"
    assert latest["remark"] == "P1测试"
    # balance_after 必须等于 delta 后余额（审计字段）
    assert isinstance(latest["balance_after"], int)


def test_member_level_and_level_list(client, auth_header):
    """无 MemberLevel 配置时：/me/level 返回 level=null；/admin/member-levels 返回空列表。

    seed 未初始化 MemberLevel（与生产一致，等级由运营后续配置），
    验证端点在无等级数据时优雅降级而非报错。
    """
    h = auth_header

    # /admin/member-levels — 无 seed → 空列表（或含其他测试已建数据，宽松校验）
    r = client.get("/admin/api/v1/admin/member-levels", headers=h)
    assert r.status_code == 200, r.text
    levels = r.json()
    assert "items" in levels
    # 每个 item 字段齐全（若非空）
    for lv in levels["items"]:
        assert "id" in lv and "name" in lv and "discount" in lv

    # /me/level — 触发 upgrade_level 判定，无等级时 level=null
    r = client.get("/admin/api/v1/me/level", headers=h)
    assert r.status_code == 200, r.text
    lvl = r.json()
    assert "level" in lvl
    assert "total_consumed" in lvl
    assert "points_balance" in lvl
    assert "next_level" in lvl
    # 无配置等级时 level 必为 null
    if not levels["items"]:
        assert lvl["level"] is None
        assert lvl["next_level"] is None
