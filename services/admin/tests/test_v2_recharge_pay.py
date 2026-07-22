"""V2.0 经销商充值真支付测试（M2.5：wechat gateway.pay + notify 回调）

monkeypatch WechatPayV3Gateway（avoid 真密钥依赖），覆盖 pay 发起 + notify 确认 + 幂等。
真验签（自签 RSA+X509）留 P0 test_wechat_pay_native 模式，M2.5 用 mock 验证业务逻辑。
"""
import uuid
from types import SimpleNamespace

from app.services.payment import PaymentResult


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


def _balance(client, dealer_h):
    return client.get("/admin/api/v2/dealer/balance", headers=dealer_h).json()


class _FakeGW:
    """mock WechatPayV3Gateway：from_settings 返实例；pay/parse_notify_safe 可控。"""

    _pay_url = "weixin://wxpay/bizpayurl"
    _notify = None

    @classmethod
    def from_settings(cls):
        return cls()

    async def pay(self, order_id, amount, subject=""):
        return PaymentResult(
            success=True,
            transaction_id=f"wx_txn_{order_id}",
            message=_FakeGW._pay_url,
        )

    def parse_notify_safe(self, headers, body):
        if _FakeGW._notify is None:
            raise RuntimeError("notify not set")
        return _FakeGW._notify


def test_recharge_pay_wechat(client, auth_header, monkeypatch):
    """wechat 充值 pending → pay 端点 mock gateway.pay 返 code_url。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"pd_{sfx}")
    _open_dealer(client, admin, dealer)
    rech = client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 100, "channel": "wechat"},
        headers=dealer,
    ).json()
    assert rech["status"] == "pending"

    monkeypatch.setattr("app.routes.v2.recharge.WechatPayV3Gateway", _FakeGW)
    r = client.post(f"/admin/api/v2/dealer/recharge/{rech['id']}/pay", headers=dealer)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pay_url"] == "weixin://wxpay/bizpayurl"
    assert data["status"] == "pending"


def test_recharge_notify_confirm(client, auth_header, monkeypatch):
    """微信回调 mock parse_notify_safe → confirm_recharge + balance += amount。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"nd_{sfx}")
    _open_dealer(client, admin, dealer)
    rech = client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 100, "channel": "wechat"},
        headers=dealer,
    ).json()
    assert float(_balance(client, dealer)["balance"]) == 0.0

    _FakeGW._notify = SimpleNamespace(
        transaction_id="wx_txn_1",
        out_trade_no=str(rech["id"]),
        amount_total_fen=10000,  # 100 元 = 10000 分
    )
    monkeypatch.setattr("app.routes.v2.recharge.WechatPayV3Gateway", _FakeGW)

    r = client.post("/admin/api/v2/dealer/recharge/notify/wechat")
    assert r.status_code == 200
    assert r.json()["code"] == "SUCCESS"
    assert float(_balance(client, dealer)["balance"]) == 100.0

    recs = client.get("/admin/api/v2/dealer/recharge", headers=dealer).json()
    assert recs[0]["status"] == "paid"


def test_recharge_notify_idempotent(client, auth_header, monkeypatch):
    """重复回调 → 幂等 ACK，balance 只加一次。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"ni_{sfx}")
    _open_dealer(client, admin, dealer)
    rech = client.post(
        "/admin/api/v2/dealer/recharge",
        json={"amount": 200, "channel": "wechat"},
        headers=dealer,
    ).json()

    _FakeGW._notify = SimpleNamespace(
        transaction_id="wx_txn_2",
        out_trade_no=str(rech["id"]),
        amount_total_fen=20000,
    )
    monkeypatch.setattr("app.routes.v2.recharge.WechatPayV3Gateway", _FakeGW)

    r1 = client.post("/admin/api/v2/dealer/recharge/notify/wechat")
    r2 = client.post("/admin/api/v2/dealer/recharge/notify/wechat")
    assert r1.status_code == 200 and r2.status_code == 200
    assert float(_balance(client, dealer)["balance"]) == 200.0  # 只加一次
