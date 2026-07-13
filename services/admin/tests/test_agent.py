"""区域代理 + 年度返佣阶梯关键路径测试（决策 #3 重构 2026-07-13）

合规边界（保留）：
- CommissionRule.rate 上限 0.5（防全额返利）
- Agent.commission_rate 上限 0.5（同上）
- 区域代理同 region_code 唯一

变更说明：
- 原 3 级分销测试已废弃（推翻为区域代理）
- 新测试覆盖区域代理 + 年度阶梯返佣关键路径
"""


def test_region_agent_creation_and_region_unique(client, auth_header):
    """区域代理：创建 + 同 region_code 唯一性"""
    h = auth_header
    r1 = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": 1,
            "name": "上海代理",
            "region_code": "TST01",
            "region_name": "上海",
            "commission_rate": 0.3,
        },
        headers=h,
    )
    assert r1.status_code == 200

    # 重复同 region_code → 400
    r2 = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": 1,
            "name": "上海二号",
            "region_code": "TST01",
            "region_name": "上海",
            "commission_rate": 0.2,
        },
        headers=h,
    )
    assert r2.status_code == 400
    assert "TST01" in r2.json()["detail"]


def test_yearly_commission_calc_t1_30_percent(client, auth_header):
    """订单完成触发单次返佣（基于年度累计阶梯 T1=30%）

    50 张 × 1321.6（7 折） = 66,080 < 50万 → T1 → 30% = 19,824
    """
    import uuid

    h = auth_header
    suffix = uuid.uuid4().hex[:4]
    region_code = f"TC{suffix}"

    # 创建区域代理
    a = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": 1,
            "name": "T1测试代理",
            "region_code": region_code,
            "region_name": "T1测试",
            "commission_rate": 0.3,
        },
        headers=h,
    ).json()

    # 创建 VIP 批次
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": f"T1-VIP-{suffix}", "type": "vip", "unit_price": 1888.0},
        headers=h,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={
            "type_id": t["id"],
            "name": f"T1批次-{suffix}",
            "quantity": 100,
            "unit_price": 1888.0,
        },
        headers=h,
    ).json()

    # 50 张 × 7 折 = 50 × 1321.6 = 66,080 元（< 50万 → T1）
    o = client.post(
        "/admin/api/v1/agent/orders",
        json={"agent_id": a["id"], "batch_id": b["id"], "quantity": 50},
        headers=h,
    ).json()
    assert float(o["total"]) == 66080.0

    # 付款 + 完成 → 触发单次返佣
    client.post(f"/admin/api/v1/agent/orders/{o['id']}/pay", headers=h)
    client.post(f"/admin/api/v1/agent/orders/{o['id']}/complete", headers=h)

    # 查返佣：66,080 × 30% = 19,824
    records = client.get("/admin/api/v1/agent/commissions/records", headers=h).json()
    order_rec = next((r for r in records["items"] if r["order_id"] == o["id"]), None)
    assert order_rec is not None
    assert abs(float(order_rec["amount"]) - 19824.0) < 0.01


# ── 合规边界防护（决策 #3 防全额返利） ──────────────────────────────


def test_commission_rule_rate_capped_at_50_percent(client, auth_header):
    """CommissionRule.rate > 0.5 必须被 pydantic 拒绝（防全额返利）。"""
    r = client.post(
        "/admin/api/v1/agent/commissions/rules",
        json={"level": 1, "rate": 0.6},  # 60% 超过上限
        headers=auth_header,
    )
    # pydantic ValidationError → 422
    assert r.status_code == 422


def test_commission_rule_rate_at_50_percent_accepted(client, auth_header):
    """边界值 0.5 应被接受。"""
    r = client.post(
        "/admin/api/v1/agent/commissions/rules",
        json={"level": 1, "rate": 0.5},
        headers=auth_header,
    )
    # 创建/upsert 都可能（首次创建 200，已存在则 200）
    assert r.status_code == 200


def test_agent_commission_rate_capped_at_50_percent(client, auth_header):
    """Agent.commission_rate > 0.5 必须被拒绝。"""
    import uuid

    r = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": 1,
            "name": "高返佣代理",
            "region_code": f"HI{uuid.uuid4().hex[:4]}",
            "region_name": "测试",
            "commission_rate": 0.8,  # 80% 超过上限
        },
        headers=auth_header,
    )
    assert r.status_code == 422


def test_agent_commission_rate_at_50_percent_accepted(client, auth_header):
    """Agent.commission_rate = 0.5 应被接受（边界值）。"""
    import uuid

    r = client.post(
        "/admin/api/v1/agent/agents",
        json={
            "user_id": 1,
            "name": "边界返佣代理",
            "region_code": f"BD{uuid.uuid4().hex[:4]}",
            "region_name": "测试",
            "commission_rate": 0.5,
        },
        headers=auth_header,
    )
    assert r.status_code == 200
