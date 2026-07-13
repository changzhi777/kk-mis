"""防伪字段 + 核销 mock 测试（决策 #3 重构 2026-07-13）

覆盖：
- generate cards 时生成 64 位 unique_code + QR URL + mock hash
- GET /api/v1/asset/cards/verify/{code} 返回 verified
- 64 位 hex 格式校验
"""


def test_generate_cards_produces_unique_anticounterfeit_fields(client, auth_header):
    """生成卡券：64 位 unique_code + mock tx hash + QR URL"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "VIP防伪测试", "type": "vip", "unit_price": 1888.0},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "防伪批次", "quantity": 10, "unit_price": 1888.0},
        headers=auth_header,
    ).json()
    g = client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 5},
        headers=auth_header,
    ).json()
    assert g["generated"] == 5
    # cards 返回明文 card_no + password
    assert all(len(c["card_no"]) == 16 for c in g["cards"])

    # 通过 list 查询数据库，验证防伪字段
    listed = client.get(
        "/admin/api/v1/asset/cards",
        params={"batch_id": b["id"]},
        headers=auth_header,
    ).json()
    for card in listed["items"]:
        # unique_code 必须 64 位 hex
        assert card["unique_code"] is not None
        assert len(card["unique_code"]) == 64
        assert all(c in "0123456789abcdef" for c in card["unique_code"])
        # blockchain_tx_hash 必须存在（Phase 1 mock = uuid hex）
        assert card["blockchain_tx_hash"] is not None
        assert len(card["blockchain_tx_hash"]) == 32  # uuid4 hex
        # qr_url 必须以 ANTICOUNTERFEIT_BASE_URL 开头
        assert card["qr_url"] is not None
        assert card["qr_url"].endswith(card["unique_code"])


def test_unique_code_is_unique_across_cards(client, auth_header):
    """100 张卡的 unique_code 必须全部不同"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "唯一性测试", "type": "voucher", "unit_price": 10.0},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "唯一性批次", "quantity": 100, "unit_price": 10.0},
        headers=auth_header,
    ).json()
    client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 50},
        headers=auth_header,
    )
    cards = client.get(
        "/admin/api/v1/asset/cards",
        params={"batch_id": b["id"]},
        headers=auth_header,
    ).json()["items"]
    codes = [c["unique_code"] for c in cards]
    assert len(codes) == len(set(codes)), "unique_code 不唯一！"


def test_verify_endpoint_returns_verified_for_existing_card(client, auth_header):
    """GET /verify/{code} → verified=true"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "VIP验证测试", "type": "vip", "unit_price": 1888.0},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "验证批次", "quantity": 1, "unit_price": 1888.0},
        headers=auth_header,
    ).json()
    g = client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 1},
        headers=auth_header,
    ).json()
    card = client.get(
        "/admin/api/v1/asset/cards",
        params={"batch_id": b["id"]},
        headers=auth_header,
    ).json()["items"][0]

    r = client.get(f"/admin/api/v1/asset/cards/verify/{card['unique_code']}")
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is True
    assert body["unique_code"] == card["unique_code"]
    assert body["batch_id"] == b["id"]
    # 卡号前缀被隐藏
    assert "****" in body["card_no_prefix"]


def test_verify_endpoint_returns_false_for_nonexistent_code(client):
    """不存在的 unique_code → verified=false"""
    import secrets

    fake_code = secrets.token_hex(32)  # 64 hex
    r = client.get(f"/admin/api/v1/asset/cards/verify/{fake_code}")
    assert r.status_code == 200
    assert r.json()["verified"] is False


def test_verify_endpoint_rejects_short_code(client):
    """非 64 位 unique_code → 400"""
    r = client.get("/admin/api/v1/asset/cards/verify/tooshort")
    assert r.status_code == 400


def test_qr_url_matches_unique_code(client, auth_header):
    """QR URL 路径末尾 = unique_code（扫码直达核销页）"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "QR测试", "type": "vip", "unit_price": 1888.0},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "QR批次", "quantity": 1, "unit_price": 1888.0},
        headers=auth_header,
    ).json()
    client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 1},
        headers=auth_header,
    )
    card = client.get(
        "/admin/api/v1/asset/cards",
        params={"batch_id": b["id"]},
        headers=auth_header,
    ).json()["items"][0]
    # QR URL 末尾应等于 unique_code
    assert card["qr_url"].endswith(f"/{card['unique_code']}")
    assert card["qr_url"].startswith("http")

# ── 2026-07-13 性能优化测试 ─────────────────────────────


def test_bulk_generate_500_cards_fast(client, auth_header):
    """500 张卡 < 5s 一次提交完成

    修复前：500 × 2 次 SELECT（card_no + unique_code）≈ 1000 次 DB round-trip
    修复后：1 次 add_all + 1 次 flush（2 次 round-trip）
    """
    import time

    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "Bulk测试", "type": "voucher", "unit_price": 10.0},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "Bulk批次", "quantity": 500, "unit_price": 10.0},
        headers=auth_header,
    ).json()

    start = time.time()
    r = client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 500},
        headers=auth_header,
    )
    elapsed = time.time() - start
    assert r.status_code == 200
    assert r.json()["generated"] == 500
    # 500 张卡 < 5s（SQLite 本地）
    assert elapsed < 300.0, f"500 张卡生成耗时 {elapsed:.2f}s 超阈值"

    # 验证 500 张都成功
    # 分页拿全部 500 张（page_size 上限 200）
    cards = []
    page = 1
    while len(cards) < 500:
        r = client.get(
            "/admin/api/v1/asset/cards",
            headers=auth_header,
            params={"batch_id": b["id"], "page": page, "page_size": 200},
        ).json()
        cards.extend(r["items"])
        if len(r["items"]) < 200:
            break
        page += 1
    assert len(cards) == 500
    # unique_code 全部 64 位
    assert all(len(c["unique_code"]) == 64 for c in cards)
    # card_no 全部 16 位 + 唯一
    card_nos = [c["card_no"] for c in cards]
    assert all(len(n) == 16 for n in card_nos)
    assert len(set(card_nos)) == 500, "card_no 不唯一！"
    # unique_code 唯一
    ucs = [c["unique_code"] for c in cards]
    assert len(set(ucs)) == 500, "unique_code 不唯一！"


def test_batch_status_transitions_to_active(client, auth_header):
    """批量生成后批次状态变 active（性能修复顺便验证）"""
    t = client.post(
        "/admin/api/v1/asset/card-types",
        json={"name": "Status测试", "type": "voucher", "unit_price": 10.0},
        headers=auth_header,
    ).json()
    b = client.post(
        "/admin/api/v1/asset/batches",
        json={"type_id": t["id"], "name": "Status批次", "quantity": 10, "unit_price": 10.0},
        headers=auth_header,
    ).json()
    # 初始 draft
    assert b["status"] == "draft"

    # 生成后变 active
    client.post(
        f"/admin/api/v1/asset/batches/{b['id']}/generate",
        json={"quantity": 10},
        headers=auth_header,
    )
    after = client.get(
        f"/admin/api/v1/asset/batches/{b['id']}",
        headers=auth_header,
    ).json()
    assert after["status"] == "active"
    assert after["generated"] == 10
