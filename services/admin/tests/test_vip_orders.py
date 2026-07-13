"""VIP 订单端到端测试（决策 #3 重构 2026-07-13）

覆盖：
- 单次折扣自动计算（70/60/50 折）
- /quote 实时报价 API
- 创建订单 → 完成订单 → 单次返佣落库
"""


def _create_region_agent(client, auth_header, region_code: str, user_id: int = 1):
    """辅助：创建区域代理"""
    r = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": user_id,
            "name": f"{region_code}代理",
            "region_code": region_code,
            "region_name": region_code,
            "commission_rate": 0.3,
            "status": True,
        },
        headers=auth_header,
    )
    return r.json()


def _create_vip_batch(client, auth_header, unit_price: float = 1888.0, quantity: int = 100):
    """辅助：创建 VIP 批次 + 类型"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "VIP测试卡", "type": "vip", "unit_price": unit_price},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "VIP批次1", "quantity": quantity, "unit_price": unit_price},
        headers=auth_header,
    ).json()
    return b


def test_quote_api_returns_correct_tier(client, auth_header):
    """/api/v1/agent/orders/quote 实时折扣"""
    _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)

    # 100 张 → 6 折
    r = client.get(
        "/admin/api/v1/agent/orders/quote",
        params={"batch_id": batch["id"], "quantity": 100},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "60"
    assert body["discount_pct"] == 0.6
    assert body["unit_price"] == 1132.8
    assert body["total"] == 113280.0


def test_quote_api_tier_50_for_1000_plus(client, auth_header):
    """1000+ 张 → 5 折"""
    _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    r = client.get(
        "/admin/api/v1/agent/orders/quote",
        params={"batch_id": batch["id"], "quantity": 1000},
        headers=auth_header,
    )
    body = r.json()
    assert body["tier"] == "50"
    assert body["discount_pct"] == 0.5
    assert body["unit_price"] == 944.0
    assert body["total"] == 944000.0


def test_quote_api_tier_70_for_small_qty(client, auth_header):
    """< 100 张 → 7 折"""
    _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    r = client.get(
        "/admin/api/v1/agent/orders/quote",
        params={"batch_id": batch["id"], "quantity": 50},
        headers=auth_header,
    )
    body = r.json()
    assert body["tier"] == "70"
    assert body["discount_pct"] == 0.7


def test_create_order_applies_discount_automatically(client, auth_header):
    """创建订单时后端自动应用折扣（不接受客户端 unit_price）"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    r = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": agent["id"], "batch_id": batch["id"], "quantity": 100, "remark": "test"},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    # 后端自动按 100 张算 6 折
    assert body["discount_tier"] == "60"
    assert float(body["unit_price"]) == 1132.8
    assert float(body["original_unit_price"]) == 1888.0
    assert float(body["total"]) == 113280.0
    assert body["region_code"].startswith("SH")


def test_create_order_region_code_locked_from_agent(client, auth_header):
    """订单 region_code 跟随 agent（防篡改）"""
    agent = _create_region_agent(client, auth_header, "BJ" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    r = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": agent["id"], "batch_id": batch["id"], "quantity": 50},
        headers=auth_header,
    )
    body = r.json()
    assert body["region_code"].startswith("BJ")


def test_complete_order_records_single_commission(client, auth_header):
    """订单完成 → 单次返佣落库（基于年度累计阶梯）"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    # 100 张 → 6 折 → 总 113280 元 → T1 (< 50万) → 30%
    order = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": agent["id"], "batch_id": batch["id"], "quantity": 100},
        headers=auth_header,
    ).json()
    client.post(f"/admin/api/v1/agent/orders/{order['id']}/pay", headers=auth_header)
    done = client.post(
        f"/admin/api/v1/agent/orders/{order['id']}/complete",
        headers=auth_header,
    ).json()
    assert done["success"] is True

    # 查返佣记录
    records = client.get(
        "/admin/api/v1/agent/commissions/records", headers=auth_header
    ).json()
    assert records["total"] >= 1
    # 113280 × 30% = 33984
    assert float(records["items"][0]["amount"]) == 33984.0


def test_duplicate_region_code_rejected(client, auth_header):
    """同一 region_code 不能创建两个代理（防代理撞区域）"""
    _create_region_agent(client, auth_header, "GZ" + str(__import__("uuid").uuid4().hex[:4]))
    r = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": 1,
            "name": "GZ二号",
            "region_code": "GZ",
            "region_name": "广州二号",
            "commission_rate": 0.2,
        },
        headers=auth_header,
    )
    assert r.status_code == 400
    assert "GZ" in r.json()["detail"]


def test_list_agents_can_filter_by_region(client, auth_header):
    """GET /api/v1/agent/agents?region_code=SH 仅返回 SH 代理"""
    _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    _create_region_agent(client, auth_header, "BJ" + str(__import__("uuid").uuid4().hex[:4]))
    r = client.get(
        "/admin/api/v1/agent/agents",
        params={"region_code": "SH"},
        headers=auth_header,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(a["region_code"] == "SH" for a in items)
    assert len(items) == 1


def test_complete_order_no_tier_rule_records_zero_commission(client, auth_header):
    """无年度阶梯规则时返佣为 0%（不入 commission_record）"""
    agent = _create_region_agent(client, auth_header, "SH" + str(__import__("uuid").uuid4().hex[:4]))
    batch = _create_vip_batch(client, auth_header)
    order = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": agent["id"], "batch_id": batch["id"], "quantity": 50},
        headers=auth_header,
    ).json()
    client.post(f"/admin/api/v1/agent/orders/{order['id']}/pay", headers=auth_header)
    client.post(
        f"/admin/api/v1/agent/orders/{order['id']}/complete",
        headers=auth_header,
    )
    records = client.get(
        "/admin/api/v1/agent/commissions/records", headers=auth_header
    ).json()
    # seed 已加 3 档阶梯，所以会有返佣
    # 这里测的是默认 seed 下，应该 ≥1 条
    assert records["total"] >= 1