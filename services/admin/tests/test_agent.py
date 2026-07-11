"""代理分润关键路径测试（建代理→订单→完成→分润计算）"""


def test_commission_calc(client, auth_header):
    """订单完成触发分润：一级20% → 金额正确"""
    h = auth_header
    # 分润规则 一级20%
    client.post("/admin/api/v1/agent/commissions/rules", json={"level": 1, "rate": 0.20}, headers=h)
    # 建代理（admin user_id=1，一级）
    a = client.post(
        "/admin/api/v1/agent/agents",
        json={"user_id": 1, "name": "总代A", "level": 1, "commission_rate": 0.20},
        headers=h,
    ).json()
    # 建批次（订单进货用）
    t = client.post("/admin/api/v1/asset/card-types", json={"name": "T", "type": "voucher"}, headers=h).json()
    b = client.post("/admin/api/v1/asset/batches", json={"type_id": t["id"], "name": "B", "quantity": 100}, headers=h).json()
    # 建订单 100×10=1000
    o = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": a["id"], "batch_id": b["id"], "quantity": 100, "unit_price": 10},
        headers=h,
    ).json()
    assert float(o["total"]) == 1000.0
    # 付款 + 完成
    client.post(f"/admin/api/v1/agent/orders/{o['id']}/pay", headers=h)
    done = client.post(f"/admin/api/v1/agent/orders/{o['id']}/complete", headers=h).json()
    assert done["success"] is True
    # 查分润：一级 1000×20% = 200
    records = client.get("/admin/api/v1/agent/commissions/records", headers=h).json()
    assert records["total"] >= 1
    amount = float(records["items"][0]["amount"])
    assert amount == 200.0


def test_second_level_agent_requires_parent(client, auth_header):
    """二级代理必须有上级（一级）"""
    r = client.post(
        "/admin/api/v1/agent/agents",
        json={"user_id": 1, "name": "二级", "level": 2, "commission_rate": 0.10},
        headers=auth_header,
    )
    assert r.status_code == 400  # 无 parent_id
