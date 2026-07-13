"""年度返佣结算测试（决策 #3 重构 2026-07-13）"""


def _create_region_agent(client, auth_header, region_code: str, user_id: int = 1):
    r = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": user_id,
            "name": f"{region_code}代理",
            "region_code": region_code,
            "region_name": region_code,
            "commission_rate": 0.3,
        },
        headers=auth_header,
    )
    return r.json()


def _create_vip_batch(client, auth_header, unit_price: float = 1888.0):
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "VIP测试卡", "type": "vip", "unit_price": unit_price},
        headers=auth_header,
    ).json()
    return client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "VIP批次1", "quantity": 100, "unit_price": unit_price},
        headers=auth_header,
    ).json()


def _create_and_complete_order(client, auth_header, agent_id, batch_id, quantity):
    """辅助：创建订单 → 付款 → 完成"""
    order = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": agent_id, "batch_id": batch_id, "quantity": quantity},
        headers=auth_header,
    ).json()
    client.post(f"/admin/api/v1/agent/orders/{order['id']}/pay", headers=auth_header)
    client.post(
        f"/admin/api/v1/agent/orders/{order['id']}/complete",
        headers=auth_header,
    )
    return order


def test_list_yearly_commissions_empty_initially(client, auth_header):
    """初次查询某年（无订单）→ 空记录"""
    year = 2099  # 未来年份确保无数据
    r = client.get(
        "/admin/api/v1/agent/yearly-commission",
        params={"year": year},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["year"] == year


def test_settle_yearly_commissions_writes_tier_correctly(client, auth_header):
    """结算触发：年度累计 10 万 → T1 (30%)"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    # 50 张 × 7 折 = 50 × 1321.6 = 66080 元
    _create_and_complete_order(client, auth_header, agent["id"], batch["id"], 50)

    # 结算当前年
    import datetime

    year = datetime.datetime.now().year
    r = client.post(
        "/admin/api/v1/agent/yearly-commission/settle",
        params={"year": year},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == year
    assert body["settled_count"] >= 1
    # 找到该 agent 的记录
    rec = next(
        (r for r in body["items"] if r["agent_id"] == agent["id"]),
        None,
    )
    assert rec is not None
    # 66080 < 50万 → T1 → 30%
    assert rec["tier"] == "T1"
    assert float(rec["commission_pct"]) == 0.30
    assert float(rec["amount"]) == 66080.0 * 0.30  # 19824
    assert rec["region_code"].startswith("SH")


def test_settle_yearly_commissions_tier_2_at_50w(client, auth_header):
    """累计 ≥ 50 万 → T2 (40%)"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    # 400 张 × 6 折 = 400 × 1132.8 = 453120 元（< 50万 → T1，不是 T2）
    # 实际要 ≥ 50万：450 × 6 折 = 509760 元 → 命中 T2
    _create_and_complete_order(client, auth_header, agent["id"], batch["id"], 450)

    import datetime

    year = datetime.datetime.now().year
    r = client.post(
        "/admin/api/v1/agent/yearly-commission/settle",
        params={"year": year},
        headers=auth_header,
    )
    rec = next(
        (r for r in r.json()["items"] if r["agent_id"] == agent["id"]),
        None,
    )
    assert float(rec["total_sales"]) == 509760.0
    assert rec["tier"] == "T2"
    assert float(rec["commission_pct"]) == 0.40
    assert float(rec["amount"]) == 509760.0 * 0.40  # 203904


def test_settle_yearly_commissions_tier_3_above_200w(client, auth_header):
    """累计 ≥ 200 万 → T3 (50%)"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    # 2500 张 × 5 折（>1000 张）= 2500 × 944 = 2,360,000 元 → T3
    _create_and_complete_order(client, auth_header, agent["id"], batch["id"], 2500)

    import datetime

    year = datetime.datetime.now().year
    r = client.post(
        "/admin/api/v1/agent/yearly-commission/settle",
        params={"year": year},
        headers=auth_header,
    )
    rec = next(
        (r for r in r.json()["items"] if r["agent_id"] == agent["id"]),
        None,
    )
    assert float(rec["total_sales"]) >= 2_000_000
    assert rec["tier"] == "T3"
    assert float(rec["commission_pct"]) == 0.50


def test_settle_dry_run_does_not_write(client, auth_header):
    """dry_run=True 不写入 DB"""
    # 用未来年份避免被前面的测试数据污染
    test_year = 2098

    r = client.post(
        "/admin/api/v1/agent/yearly-commission/settle",
        params={"year": test_year, "dry_run": "true"},
        headers=auth_header,
    )
    body = r.json()
    assert body["dry_run"] is True
    assert body["settled_count"] == 0

    # 真查询该年应为空（dry_run 没写）
    r2 = client.get(
        "/admin/api/v1/agent/yearly-commission",
        params={"year": test_year},
        headers=auth_header,
    )
    assert r2.json()["count"] == 0


def test_settle_yearly_aggregates_multiple_orders(client, auth_header):
    """年度返佣累计多笔订单"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    # 3 笔 30 张订单 = 90 张 × 1321.6 = 118944 元
    for _ in range(3):
        _create_and_complete_order(client, auth_header, agent["id"], batch["id"], 30)

    import datetime

    year = datetime.datetime.now().year
    client.post(
        "/admin/api/v1/agent/yearly-commission/settle",
        params={"year": year},
        headers=auth_header,
    )

    records = client.get(
        "/admin/api/v1/agent/yearly-commission",
        params={"year": year},
        headers=auth_header,
    ).json()
    rec = next(
        (r for r in records["items"] if r["agent_id"] == agent["id"]),
        None,
    )
    assert rec["order_count"] == 3
    assert float(rec["total_sales"]) == 118944.0


def test_filter_yearly_commission_by_region(client, auth_header):
    """GET ?region_code=SH 仅返回 SH 区域"""
    a_sh = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    a_bj = _create_region_agent(client, auth_header, "BJ" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    _create_and_complete_order(client, auth_header, a_sh["id"], batch["id"], 50)
    _create_and_complete_order(client, auth_header, a_bj["id"], batch["id"], 50)

    import datetime

    year = datetime.datetime.now().year
    client.post(
        "/admin/api/v1/agent/yearly-commission/settle",
        params={"year": year},
        headers=auth_header,
    )

    r = client.get(
        "/admin/api/v1/agent/yearly-commission",
        params={"year": year, "region_code": "SH"},
        headers=auth_header,
    )
    items = r.json()["items"]
    assert all(it["region_code"] == "SH" for it in items)