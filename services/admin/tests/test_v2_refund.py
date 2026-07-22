"""V2.0 经销商退款测试（M3.3 F16：激活后取消，退余额 + membership/ac refunded）

覆盖：激活后退款(余额回退+membership refunded) / 已核销退款409 / 非归属经销商403 /
pending 授权码退款409 / 重复退款409。
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


def _create_pass(client, admin_h, face_value=100):
    sfx = uuid.uuid4().hex[:6]
    return client.post(
        "/admin/api/v1/cms/products",
        json={
            "title": f"套餐_{sfx}",
            "slug": f"pkg-{sfx}",
            "type": "pass",
            "status": "published",
            "pass_config": {"face_value": face_value, "total_worth": face_value},
        },
        headers=admin_h,
    ).json()["id"]


def _balance(client, dealer_h):
    return client.get("/admin/api/v2/dealer/balance", headers=dealer_h).json()


def _setup_activated(client, admin_h, dealer=None, customer=None):
    """经销商充值+推广码+套餐+客户激活，返回 (dealer_h, customer_h, promo, pid, ac)。"""
    sfx = uuid.uuid4().hex[:6]
    dealer = dealer or _register(client, f"rfd_{sfx}")
    _open_dealer(client, admin_h, dealer)
    client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 1000, "channel": "mock"},
        headers=dealer,
    )
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin_h, 100)
    customer = customer or _register(client, f"rfc_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer)
    return dealer, customer, promo, pid, ac


def test_refund_after_activation(client, auth_header):
    """激活后退款：balance 回退 + membership/ac refunded。"""
    admin = auth_header
    dealer, customer, _, _, ac = _setup_activated(client, admin)
    # 激活扣 100，余额 900
    assert float(_balance(client, dealer)["balance"]) == 900.0

    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=dealer)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "refunded"
    # 退款回 100，余额 1000
    assert float(_balance(client, dealer)["balance"]) == 1000.0
    m = client.get("/admin/api/v2/membership", headers=customer).json()
    assert m[0]["status"] == "refunded"


def test_refund_after_redeem_409(client, auth_header):
    """已核销（membership used）退款 → 409。"""
    admin = auth_header
    dealer, customer, _, pid, ac = _setup_activated(client, admin)
    tg = client.post(
        "/admin/api/v2/tour-groups",
        json={
            "product_id": pid,
            "title": "T",
            "start_date": "2026-10-01T00:00:00",
            "end_date": "2026-10-07T00:00:00",
            "capacity": 10,
        },
        headers=admin,
    ).json()
    res = client.post(
        "/admin/api/v2/reservation",
        json={"tour_group_id": tg["id"], "activation_code_id": ac["id"], "people_count": 1},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/reservation/{res['id']}/redeem", headers=admin)

    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=dealer)
    assert r.status_code == 409


def test_refund_wrong_dealer_403(client, auth_header):
    """非归属经销商退款 → 403。"""
    admin = auth_header
    _, _, _, _, ac = _setup_activated(client, admin)
    other = _register(client, f"ro_{uuid.uuid4().hex[:6]}")
    _open_dealer(client, admin, other)
    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=other)
    assert r.status_code == 403


def test_refund_not_activated_409(client, auth_header):
    """pending 授权码（未激活）退款 → 409。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"rn_{sfx}")
    _open_dealer(client, admin, dealer)
    client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 1000, "channel": "mock"},
        headers=dealer,
    )
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin)
    customer = _register(client, f"rnc_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()  # pending（未 initiate/confirm）

    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=dealer)
    assert r.status_code == 409


def test_refund_double_409(client, auth_header):
    """重复退款 → 409。"""
    admin = auth_header
    dealer, _, _, _, ac = _setup_activated(client, admin)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=dealer)
    r = client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=dealer)
    assert r.status_code == 409
