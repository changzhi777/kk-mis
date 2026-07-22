"""V2.0 经销商工作台 + 月度对账测试（M3.4/M3.5 数据聚合）"""
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


def _setup_with_activation_and_rebate(client, admin_h):
    """经销商充值+激活1笔+月结返点，返回 (dealer_h, customer_h)。"""
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"db_{sfx}")
    _open_dealer(client, admin_h, dealer)
    client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 1000, "channel": "mock"},
        headers=dealer,
    )
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin_h, 100)
    customer = _register(client, f"dc_{sfx}")
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer)
    # 月结返点（R1 5% × 100 = 5）
    client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer)
    return dealer, customer


def test_dashboard(client, auth_header):
    """工作台聚合：余额/激活数/累计返点。"""
    dealer, _ = _setup_with_activation_and_rebate(client, auth_header)
    d = client.get("/admin/api/v2/dealer/dashboard", headers=dealer)
    assert d.status_code == 200, d.text
    data = d.json()
    # 充值 1000 - 激活 100 + 返点 5 = 905
    assert float(data["balance"]) == 905.0
    assert float(data["total_consumed"]) == 100.0
    assert data["activated_count"] == 1
    assert float(data["total_rebate"]) == 5.0


def test_statement(client, auth_header):
    """月度对账：激活明细 + 返点记录。"""
    dealer, _ = _setup_with_activation_and_rebate(client, auth_header)
    s = client.get("/admin/api/v2/dealer/statement", headers=dealer)
    assert s.status_code == 200, s.text
    data = s.json()
    assert len(data["activations"]) == 1
    assert float(data["total_sales"]) == 100.0
    assert data["rebate"] is not None
    assert data["rebate"]["tier"] == "R1"
    assert float(data["rebate"]["amount"]) == 5.0


def test_statement_bad_period_400(client, auth_header):
    """period 格式错 → 400。"""
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"bp_{sfx}")
    _open_dealer(client, auth_header, dealer)
    r = client.get("/admin/api/v2/dealer/statement?period=bad", headers=dealer)
    assert r.status_code == 400


def test_dashboard_requires_dealer(client, auth_header):
    """非经销商查工作台 → 403。"""
    plain = _register(client, f"nd_{uuid.uuid4().hex[:6]}")
    assert (
        client.get("/admin/api/v2/dealer/dashboard", headers=plain).status_code
        == 403
    )
