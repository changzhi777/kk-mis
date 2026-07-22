"""V2.0 客户权益 + 核销测试（M3.2：激活后建 membership，核销 used）

覆盖：激活 confirm 建 membership active / 预约+核销 reservation→used + membership→used /
重复核销 409 / 非超管核销 403 / 权益列表。
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


def _create_tour_group(client, admin_h, product_id, capacity=20, hotel=10, car=5):
    return client.post(
        "/admin/api/v2/tour-groups",
        json={
            "product_id": product_id,
            "title": "国庆团",
            "start_date": "2026-10-01T00:00:00",
            "end_date": "2026-10-07T00:00:00",
            "capacity": capacity,
            "hotel_qty": hotel,
            "car_qty": car,
        },
        headers=admin_h,
    ).json()


def _full_activation(client, admin_h, dealer_h, customer_h, promo, pid):
    """完整激活流，返回 activation_code（含 id）。"""
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer_h,
    ).json()
    client.post(
        f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer_h
    )
    client.post(
        f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer_h
    )
    return ac


def _setup_activated_customer(client, admin_h):
    """开通经销商 + 充值 + 推广码 + 套餐 + 客户激活，返回 (dealer_h, customer_h, promo, pid, ac)。"""
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"md_{sfx}")
    _open_dealer(client, admin_h, dealer)
    client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 1000, "channel": "mock"},
        headers=dealer,
    )
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()[
        "promo_code"
    ]
    pid = _create_pass(client, admin_h)
    customer = _register(client, f"mc_{sfx}")
    ac = _full_activation(client, admin_h, dealer, customer, promo, pid)
    return dealer, customer, promo, pid, ac


def test_activation_creates_membership(client, auth_header):
    """激活 confirm 后建 membership（active）。"""
    _, customer, _, _, _ = _setup_activated_customer(client, auth_header)
    m = client.get("/admin/api/v2/membership", headers=customer).json()
    assert len(m) == 1
    assert m[0]["status"] == "active"
    assert m[0]["activated_at"] is not None


def test_redeem_full_flow(client, auth_header):
    """预约(带 activation_code_id) + 核销 → reservation used + membership used。"""
    admin = auth_header
    _, customer, _, pid, ac = _setup_activated_customer(client, admin)
    tg = _create_tour_group(client, admin, pid)
    res = client.post(
        "/admin/api/v2/reservation",
        json={
            "tour_group_id": tg["id"],
            "activation_code_id": ac["id"],
            "people_count": 1,
        },
        headers=customer,
    ).json()
    assert res["status"] == "confirmed"

    redeemed = client.post(
        f"/admin/api/v2/reservation/{res['id']}/redeem", headers=admin
    ).json()
    assert redeemed["status"] == "used"

    m = client.get("/admin/api/v2/membership", headers=customer).json()
    assert m[0]["status"] == "used"
    assert m[0]["reservation_id"] == res["id"]


def test_redeem_not_confirmed_409(client, auth_header):
    """重复核销（已 used）→ 409。"""
    admin = auth_header
    _, customer, _, pid, ac = _setup_activated_customer(client, admin)
    tg = _create_tour_group(client, admin, pid)
    res = client.post(
        "/admin/api/v2/reservation",
        json={"tour_group_id": tg["id"], "activation_code_id": ac["id"], "people_count": 1},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/reservation/{res['id']}/redeem", headers=admin)
    r = client.post(f"/admin/api/v2/reservation/{res['id']}/redeem", headers=admin)
    assert r.status_code == 409


def test_redeem_permission(client, auth_header):
    """非超管核销 → 403。"""
    admin = auth_header
    _, customer, _, pid, ac = _setup_activated_customer(client, admin)
    tg = _create_tour_group(client, admin, pid)
    res = client.post(
        "/admin/api/v2/reservation",
        json={"tour_group_id": tg["id"], "activation_code_id": ac["id"], "people_count": 1},
        headers=customer,
    ).json()
    r = client.post(f"/admin/api/v2/reservation/{res['id']}/redeem", headers=customer)
    assert r.status_code == 403
