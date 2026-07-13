"""卡券核销关键路径测试（建类型→批次→生成→发放→核销）"""


def _create_and_issue(client, h):
    """辅助：建类型+批次+生成1张+发放，返回 (card_no, card_id)"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "测试券", "type": "voucher", "face_value": 50, "valid_days": 30},
        headers=h,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "测试批次", "quantity": 10},
        headers=h,
    ).json()
    g = client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 1},
        headers=h,
    ).json()
    card_no = g["cards"][0]["card_no"]
    # 查卡券 id
    cards = client.get("/admin/api/v1/asset/cards", params={"keyword": card_no}, headers=h).json()
    card_id = cards["items"][0]["id"]
    # 发放
    client.post(f"/admin/api/v1/asset/cards/{card_id}/issue", json={"holder_user_id": 1}, headers=h)
    return card_no, card_id


def test_generate_cards(client, auth_header):
    """生成卡券：返回明文卡号16位 + 密码6位"""
    t = client.post("/admin/api/v1/asset/card-types", json={"name": "T", "type": "voucher"}, headers=auth_header).json()
    b = client.post("/admin/api/v1/asset/batches", json={"type_id": t["id"], "name": "B", "quantity": 5}, headers=auth_header).json()
    g = client.post(f"/admin/api/v1/asset/batches/{b['id']}/generate", json={"quantity": 3}, headers=auth_header).json()
    assert g["generated"] == 3
    assert len(g["cards"][0]["card_no"]) == 16
    assert len(g["cards"][0]["password"]) == 6


def test_redeem_scan(client, auth_header):
    """扫码核销：issued→used"""
    card_no, _ = _create_and_issue(client, auth_header)
    r = client.post(
        "/admin/api/v1/asset/redemptions/redeem",
        json={"card_no": card_no, "method": "scan"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["amount"] == 50.0


def test_redeem_wrong_card(client, auth_header):
    """核销不存在卡号：失败"""
    r = client.post(
        "/admin/api/v1/asset/redemptions/redeem",
        json={"card_no": "9999999999999999", "method": "scan"},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_redeem_twice_fails(client, auth_header):
    """重复核销：第二次失败（状态非 issued）"""
    card_no, _ = _create_and_issue(client, auth_header)
    client.post("/admin/api/v1/asset/redemptions/redeem", json={"card_no": card_no, "method": "scan"}, headers=auth_header)
    r2 = client.post("/admin/api/v1/asset/redemptions/redeem", json={"card_no": card_no, "method": "scan"}, headers=auth_header)
    assert r2.status_code == 400


def test_card_type_supports_all_4_kinds(client, auth_header):
    """卡券类型覆盖 4 种（VIP / voucher代金 / redemption兑换 / stored储值）— 决策落地验证。"""
    h = auth_header
    for kind in ["vip", "voucher", "exchange", "stored"]:
        r = client.post(
            "/admin/api/v1/asset/card-types",
            json={"name": f"测试-{kind}", "type": kind},
            headers=h,
        )
        assert r.status_code == 200, f"类型 {kind} 建失败: {r.text}"
        assert r.json()["type"] == kind
