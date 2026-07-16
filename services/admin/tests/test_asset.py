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


# ── H15（2026-07-16）：卡转赠两步确认状态机 ──────────────────────────────


def _login_headers(client, username: str, password: str) -> dict:
    """辅助：登录拿任意用户的 auth header"""
    r = client.post(
        "/admin/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert r.status_code == 200, f"login {username} failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_receiver(client, h, prefix="rcv"):
    """辅助：创建一个普通用户（接收人）并返回 (id, username, password)"""
    import uuid

    username = f"{prefix}_{uuid.uuid4().hex[:6]}"
    password = "pass1234"
    u = client.post(
        "/admin/api/v1/users",
        json={"username": username, "password": password, "name": "接收人"},
        headers=h,
    ).json()
    return u["id"], username, password


def test_transfer_card_pending_then_accept(client, auth_header):
    """H15：发起转赠 status=pending + holder 不变；接收人 accept 后 holder 转移"""
    h = auth_header
    uid2, uname2, pwd2 = _create_receiver(client, h)
    card_no, card_id = _create_and_issue(client, h)

    # 发起前 holder
    holder_before = client.get(
        "/admin/api/v1/asset/cards", params={"keyword": card_no}, headers=h
    ).json()["items"][0]["holder_user_id"]

    # 第 1 步：admin 发起 transfer → pending
    r = client.post(
        "/admin/api/v1/asset/redemptions/transfer-card",
        json={"card_id": card_id, "to_user_id": uid2},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    transfer_id = body["transfer_id"]

    # 关键：holder 未立即转移
    holder_mid = client.get(
        "/admin/api/v1/asset/cards", params={"keyword": card_no}, headers=h
    ).json()["items"][0]["holder_user_id"]
    assert holder_mid == holder_before, "转赠发起后 holder 不应立即变化"

    # 第 2 步：接收人 accept
    h2 = _login_headers(client, uname2, pwd2)
    r2 = client.post(
        f"/admin/api/v1/asset/redemptions/transfer-card/{transfer_id}/accept",
        headers=h2,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "accepted"

    # holder 已转移到接收人
    holder_after = client.get(
        "/admin/api/v1/asset/cards", params={"keyword": card_no}, headers=h
    ).json()["items"][0]["holder_user_id"]
    assert holder_after == uid2, "accept 后 holder 应为接收人"


def test_transfer_card_rejected_holder_unchanged(client, auth_header):
    """H15：接收人 reject → status=rejected + holder 保持原持卡人"""
    h = auth_header
    uid2, uname2, pwd2 = _create_receiver(client, h, prefix="rej")
    card_no, card_id = _create_and_issue(client, h)

    holder_before = client.get(
        "/admin/api/v1/asset/cards", params={"keyword": card_no}, headers=h
    ).json()["items"][0]["holder_user_id"]

    r = client.post(
        "/admin/api/v1/asset/redemptions/transfer-card",
        json={"card_id": card_id, "to_user_id": uid2},
        headers=h,
    )
    transfer_id = r.json()["transfer_id"]

    h2 = _login_headers(client, uname2, pwd2)
    r2 = client.post(
        f"/admin/api/v1/asset/redemptions/transfer-card/{transfer_id}/reject",
        headers=h2,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"

    holder_after = client.get(
        "/admin/api/v1/asset/cards", params={"keyword": card_no}, headers=h
    ).json()["items"][0]["holder_user_id"]
    assert holder_after == holder_before, "reject 后 holder 不应变"


def test_transfer_card_wrong_receiver_forbidden(client, auth_header):
    """H15：非接收人不可 accept/reject（403）"""
    h = auth_header
    uid2, _, _ = _create_receiver(client, h, prefix="rcv2")
    # 第三个用户（非接收人）
    uid3, uname3, pwd3 = _create_receiver(client, h, prefix="rcv3")
    card_no, card_id = _create_and_issue(client, h)

    r = client.post(
        "/admin/api/v1/asset/redemptions/transfer-card",
        json={"card_id": card_id, "to_user_id": uid2},
        headers=h,
    )
    transfer_id = r.json()["transfer_id"]

    # uid3 尝试 accept → 403
    h3 = _login_headers(client, uname3, pwd3)
    r3 = client.post(
        f"/admin/api/v1/asset/redemptions/transfer-card/{transfer_id}/accept",
        headers=h3,
    )
    assert r3.status_code == 403
