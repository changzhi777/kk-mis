"""V2.0 经销商阶梯返点测试（M2.4 月结返余额）

覆盖：R1/R2 阶梯命中 + 返点入余额 + 重复结算 409 + 记录列表。
"""
import uuid


def _register(client, username):
    pwd = "test1234"
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": username, "password": pwd, "name": username},
    )
    assert r.status_code == 200, r.text
    token = r.json().get("access_token") or client.post(
        "/admin/api/v1/auth/login",
        json={"username": username, "password": pwd},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _open_dealer(client, admin_h, dealer_h):
    app = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": "GD"},
        headers=dealer_h,
    ).json()
    client.post(f"/admin/api/v2/dealer/application/{app['id']}/approve", headers=admin_h)


def _create_pass(client, admin_h, face_value):
    sfx = uuid.uuid4().hex[:6]
    r = client.post(
        "/admin/api/v1/cms/products",
        json={
            "title": f"套餐_{sfx}",
            "slug": f"pkg-{sfx}",
            "type": "pass",
            "status": "published",
            "pass_config": {"face_value": face_value, "total_worth": face_value},
        },
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _recharge(client, dealer_h, amount):
    r = client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": amount, "channel": "mock"},
        headers=dealer_h,
    )
    assert r.status_code == 200, r.text


def _balance(client, dealer_h):
    return client.get("/admin/api/v2/dealer/balance", headers=dealer_h).json()


def _do_activation(client, dealer_h, promo, pid, customer_h):
    """完整激活流（客户生成→经销商发起→客户确认）。"""
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer_h,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer_h)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer_h)


def test_rebate_settle_r1(client, auth_header):
    """当月激活 100（< 1万）→ R1 5% → 返点 5 入余额。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"rb1d_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 1000)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin, 100)
    customer = _register(client, f"rb1c_{sfx}")
    _do_activation(client, dealer, promo, pid, customer)

    r = client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert float(rec["total_sales"]) == 100.0
    assert rec["tier"] == "R1"
    assert float(rec["rebate_pct"]) == 0.05
    assert float(rec["rebate_amount"]) == 5.0
    assert rec["status"] == "settled"
    # 充值 1000 - 激活 100 + 返点 5 = 905
    bal = _balance(client, dealer)
    assert float(bal["balance"]) == 905.0


def test_rebate_settle_r2(client, auth_header):
    """当月激活 12000（1万-5万）→ R2 10% → 返点 1200。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"rb2d_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 15000)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin, 12000)
    customer = _register(client, f"rb2c_{sfx}")
    _do_activation(client, dealer, promo, pid, customer)

    rec = client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer).json()
    assert float(rec["total_sales"]) == 12000.0
    assert rec["tier"] == "R2"
    assert float(rec["rebate_pct"]) == 0.10
    assert float(rec["rebate_amount"]) == 1200.0
    # 15000 - 12000 + 1200 = 4200
    assert float(_balance(client, dealer)["balance"]) == 4200.0


def test_rebate_already_settled(client, auth_header):
    """同月重复结算 → 409。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"rb3d_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 1000)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin, 100)
    customer = _register(client, f"rb3c_{sfx}")
    _do_activation(client, dealer, promo, pid, customer)

    r1 = client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer)
    assert r1.status_code == 200
    r2 = client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer)
    assert r2.status_code == 409


def test_rebate_list(client, auth_header):
    """结算后列表含记录。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"rb4d_{sfx}")
    _open_dealer(client, admin, dealer)
    _recharge(client, dealer, 1000)
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin, 100)
    customer = _register(client, f"rb4c_{sfx}")
    _do_activation(client, dealer, promo, pid, customer)
    client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer)

    rows = client.get("/admin/api/v2/dealer/rebate", headers=dealer).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "settled"
    assert rows[0]["tier"] == "R1"


def test_rebate_requires_dealer(client, auth_header):
    """非经销商触发月结 → 403。"""
    plain = _register(client, f"rb5_{uuid.uuid4().hex[:6]}")
    r = client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=plain)
    assert r.status_code == 403
