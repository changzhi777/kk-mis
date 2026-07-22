"""V2.0 商业闭环测试（M2.1-2.3：推广码 + 充值 + 授权码激活流）

覆盖：经销商推广码懒生成 / mock 充值 / 客户授权码生成→经销商发起(冻结)→客户确认(扣款)完整流 /
边界（非dealer403 / 余额不足409 / 非归属经销商发起403 / 非生成者确认403 / 无效推广码404 /
custom套餐400 / pending直接确认409）。

详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
import uuid


def _register(client, username: str) -> dict:
    pwd = "test1234"
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": username, "password": pwd, "name": username},
    )
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    if not token:
        token = client.post(
            "/admin/api/v1/auth/login",
            json={"username": username, "password": pwd},
        ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _open_dealer(client, admin_h, dealer_h, province="GD"):
    """经销商申请→审批开通（建 Agent + Balance）。"""
    app = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": province},
        headers=dealer_h,
    ).json()
    client.post(
        f"/admin/api/v2/dealer/application/{app['id']}/approve", headers=admin_h
    )


def _create_pass_product(client, admin_h, face_value=100, type_="pass") -> int:
    suffix = uuid.uuid4().hex[:6]
    body = {
        "title": f"测试套餐_{suffix}",
        "slug": f"test-pkg-{suffix}",
        "type": type_,
        "status": "published",
    }
    if type_ == "pass":
        body["pass_config"] = {"face_value": face_value, "total_worth": face_value}
    r = client.post("/admin/api/v1/cms/products", json=body, headers=admin_h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _recharge(client, dealer_h, amount):
    r = client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": amount, "channel": "mock"},
        headers=dealer_h,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _balance(client, dealer_h) -> dict:
    return client.get("/admin/api/v2/dealer/balance", headers=dealer_h).json()


# ── 推广码 + 充值 ──────────────────────────────────────────────


def test_promo_code_lazy_gen(client, auth_header):
    """经销商首次 GET 推广码 → 懒生成 8 位；再次 GET 同码。"""
    dealer = _register(client, f"p_{uuid.uuid4().hex[:6]}")
    _open_dealer(client, auth_header, dealer)
    r = client.get("/admin/api/v2/dealer/promo-code", headers=dealer)
    assert r.status_code == 200
    code = r.json()["promo_code"]
    assert len(code) == 8
    again = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()
    assert again["promo_code"] == code


def test_promo_code_requires_dealer(client, auth_header):
    """非经销商（未开通）GET 推广码 → 403。"""
    plain = _register(client, f"np_{uuid.uuid4().hex[:6]}")
    assert (
        client.get("/admin/api/v2/dealer/promo-code", headers=plain).status_code
        == 403
    )


def test_recharge_mock_increases_balance(client, auth_header):
    """mock 充值 200 → balance/total_recharged=200；记录 paid。"""
    dealer = _register(client, f"r_{uuid.uuid4().hex[:6]}")
    _open_dealer(client, auth_header, dealer)
    _recharge(client, dealer, 200)
    bal = _balance(client, dealer)
    assert float(bal["balance"]) == 200.0
    assert float(bal["total_recharged"]) == 200.0
    recs = client.get("/admin/api/v2/dealer/recharge", headers=dealer).json()
    assert len(recs) == 1
    assert recs[0]["status"] == "paid"


# ── 授权码激活流 ──────────────────────────────────────────────


def test_activation_full_flow(client, auth_header):
    """完整：客户生成→经销商发起(冻结)→客户确认(扣款)，余额全程验证。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"d_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 200)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()[
        "promo_code"
    ]
    pid = _create_pass_product(client, admin, face_value=100)

    # 客户生成授权码
    customer = _register(client, f"c_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    assert ac["status"] == "pending"
    assert float(ac["price"]) == 100.0
    code = ac["code"]

    # 经销商发起 → 冻结
    init = client.post(
        f"/admin/api/v2/activation/code/{code}/initiate", headers=dealer
    ).json()
    assert init["status"] == "activating"
    bal = _balance(client, dealer)
    assert float(bal["balance"]) == 100.0  # 200-100
    assert float(bal["frozen"]) == 100.0

    # 客户确认 → 扣款
    conf = client.post(
        f"/admin/api/v2/activation/code/{code}/confirm", headers=customer
    ).json()
    assert conf["status"] == "activated"
    bal2 = _balance(client, dealer)
    assert float(bal2["balance"]) == 100.0
    assert float(bal2["frozen"]) == 0.0
    assert float(bal2["total_consumed"]) == 100.0


def test_activation_insufficient_balance(client, auth_header):
    """余额不足（50 < 套餐 100）发起激活 → 409。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"d2_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 50)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()[
        "promo_code"
    ]
    pid = _create_pass_product(client, admin, face_value=100)
    customer = _register(client, f"c2_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    assert r.status_code == 409


def test_activation_wrong_dealer_initiate(client, auth_header):
    """非归属经销商发起激活 → 403。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer_a = _register(client, f"da_{sfx}")
    _open_dealer(client, admin, dealer_a)
    _recharge(client, dealer_a, 200)
    promo_a = client.get("/admin/api/v2/dealer/promo-code", headers=dealer_a).json()[
        "promo_code"
    ]
    pid = _create_pass_product(client, admin, face_value=100)
    customer = _register(client, f"cw_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo_a, "product_id": pid},
        headers=customer,
    ).json()
    # 经销商 B（非归属）发起 → 403
    dealer_b = _register(client, f"db_{sfx}")
    _open_dealer(client, admin, dealer_b)
    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer_b)
    assert r.status_code == 403


def test_activation_wrong_customer_confirm(client, auth_header):
    """非授权码生成者确认 → 403。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"d3_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 200)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()[
        "promo_code"
    ]
    pid = _create_pass_product(client, admin, face_value=100)
    customer = _register(client, f"c3_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    other = _register(client, f"co_{sfx}")
    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=other)
    assert r.status_code == 403


def test_activation_invalid_promo(client, auth_header):
    """无效推广码生成授权码 → 404。"""
    pid = _create_pass_product(client, auth_header)
    customer = _register(client, f"ci_{uuid.uuid4().hex[:6]}")
    r = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": "NOCODE999", "product_id": pid},
        headers=customer,
    )
    assert r.status_code == 404


def test_activation_custom_product_rejected(client, auth_header):
    """订制游（custom）套餐不支持授权码激活 → 400。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"d4_{sfx}")
    _open_dealer(client, admin, dealer)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()[
        "promo_code"
    ]
    pid = _create_pass_product(client, admin, type_="custom")
    customer = _register(client, f"c4_{sfx}")
    r = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    )
    assert r.status_code == 400


def test_activation_not_initiated_cannot_confirm(client, auth_header):
    """pending（未经销商发起）客户直接确认 → 409。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"d5_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 200)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()[
        "promo_code"
    ]
    pid = _create_pass_product(client, admin, face_value=100)
    customer = _register(client, f"c5_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer)
    assert r.status_code == 409
