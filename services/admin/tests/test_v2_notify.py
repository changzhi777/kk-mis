"""V2.0 事件通知测试（M3.6：激活/退款/返点 关键事件 notify）

monkeypatch 模块级 notify 为 spy，验证关键事件触发（旁路 webhook 未配置时 notify 静默，
此处验证调用契约：事件名 + payload）。
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


def _setup(client, admin_h):
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"nd_{sfx}")
    _open_dealer(client, admin_h, dealer)
    client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 1000, "channel": "mock"},
        headers=dealer,
    )
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()["promo_code"]
    pid = _create_pass(client, admin_h, 100)
    customer = _register(client, f"nc_{sfx}")
    return dealer, customer, promo, pid


def test_notify_activation_confirmed(client, auth_header, monkeypatch):
    """激活 confirm 触发 v2.activation.confirmed。"""
    events = []

    async def spy(event, data):
        events.append((event, data))

    monkeypatch.setattr("app.routes.v2.activation.notify", spy)
    dealer, customer, promo, pid = _setup(client, auth_header)
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer)

    names = [e[0] for e in events]
    assert "v2.activation.confirmed" in names
    payload = next(e[1] for e in events if e[0] == "v2.activation.confirmed")
    assert payload["activation_code_id"] == ac["id"]
    assert float(payload["price"]) == 100.0


def test_notify_refund(client, auth_header, monkeypatch):
    """退款触发 v2.refund。"""
    events = []

    async def spy(event, data):
        events.append((event, data))

    monkeypatch.setattr("app.routes.v2.activation.notify", spy)
    dealer, customer, promo, pid = _setup(client, auth_header)
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/refund", headers=dealer)

    names = [e[0] for e in events]
    assert "v2.refund" in names


def test_notify_rebate_settled(client, auth_header, monkeypatch):
    """返点月结触发 v2.rebate.settled。"""
    events = []

    async def spy(event, data):
        events.append((event, data))

    monkeypatch.setattr("app.routes.v2.rebate.notify", spy)
    dealer, customer, promo, pid = _setup(client, auth_header)
    ac = client.post(
        "/admin/api/v2/activation/code",
        json={"promo_code": promo, "product_id": pid},
        headers=customer,
    ).json()
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/initiate", headers=dealer)
    client.post(f"/admin/api/v2/activation/code/{ac['code']}/confirm", headers=customer)
    client.post("/admin/api/v2/dealer/rebate/settle", json={}, headers=dealer)

    names = [e[0] for e in events]
    assert "v2.rebate.settled" in names
    payload = next(e[1] for e in events if e[0] == "v2.rebate.settled")
    assert float(payload["rebate_amount"]) == 5.0
