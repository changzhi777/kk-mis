"""WechatPayV3Gateway 下单/退款/查单（Native）单测（P0 Day 2.5 缺口 #5，2026-07-17）。

无真商户密钥——用自签 RSA 密钥对 + 自签 X.509 平台证书构造 gateway，mock ``_request``
返回**带平台私钥签名**的响应，端到端验证：
- 请求签名（Authorization 头格式 + 商户私钥签名可被公钥验证）
- 金额换算（元→分）
- 请求体字段（appid/mchid/out_trade_no/amount）
- 应答验签（平台证书公钥，复用 verify_callback）
- 验签 fail-closed（签名被篡改 → raise）
- 响应解析（code_url / trade_state / refund status）

真连微信仍待商户密钥灰度（MCH_ID/APP_ID/API_V3_KEY/商户私钥/平台证书）。
"""
import base64
import json
import secrets
import time
from datetime import datetime, timezone

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID


# ── 一次性生成自签密钥与证书（模块级，避免每用例重算 RSA）──────────────

merchant_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
merchant_pub = merchant_priv.public_key()
platform_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)

_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wechatpay-test")])
platform_cert = (
    x509.CertificateBuilder()
    .subject_name(_subject)
    .issuer_name(_subject)
    .public_key(platform_priv.public_key())
    .serial_number(9999)
    .not_valid_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
    .not_valid_after(datetime(2030, 1, 1, tzinfo=timezone.utc))
    .sign(platform_priv, hashes.SHA256())
)
# _normalize_serial: format(serial_number, "X")
platform_serial = format(platform_cert.serial_number, "X")


def _make_gateway(with_cert: bool = False):
    from app.services.wechat_pay import WechatPayV3Gateway

    gw = WechatPayV3Gateway(
        api_v3_key=b"0" * 32,
        mch_id="1234567890",
        app_id="wxAPPID",
        mch_private_key=merchant_priv,
        mch_serial_no="MCHSERIAL",
        notify_url="https://example.com/notify",
    )
    if with_cert:
        gw._cert_map[platform_serial] = platform_cert
    return gw


def _signed_response(status: int, body_bytes: bytes) -> httpx.Response:
    """构造带平台私钥签名的 fake 响应（Wechatpay-* 头）。"""
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    sign_str = f"{ts}\n{nonce}\n".encode() + body_bytes + b"\n"
    sig = platform_priv.sign(sign_str, padding.PKCS1v15(), hashes.SHA256())
    return httpx.Response(
        status,
        content=body_bytes,
        headers={
            "Wechatpay-Timestamp": ts,
            "Wechatpay-Nonce": nonce,
            "Wechatpay-Signature": base64.b64encode(sig).decode(),
            "Wechatpay-Serial": platform_serial,
            "Content-Type": "application/json",
        },
    )


# ── 金额换算 ──────────────────────────────────────────────────

def test_to_fen():
    gw = _make_gateway()
    assert gw._to_fen(1.23) == 123
    assert gw._to_fen("0.01") == 1
    assert gw._to_fen(100) == 10000
    assert gw._to_fen(0.1) == 10  # float 精度：经 Decimal(str()) 规避


# ── 请求签名 ──────────────────────────────────────────────────

def test_build_authorization_format_and_signature():
    gw = _make_gateway()
    auth = gw._build_authorization("POST", "/v3/pay/transactions/native", '{"a":1}')
    assert auth.startswith("WECHATPAY2-SHA256-RSA2048 ")
    assert 'mchid="1234567890"' in auth
    assert 'serial_no="MCHSERIAL"' in auth

    # 提取字段，用商户公钥验证签名（证明签名串格式 + 私钥签名有效）
    import re
    fields = dict(re.findall(r'(\w+)="([^"]*)"', auth.split(" ", 1)[1]))
    ts, nonce, sig_b64 = fields["timestamp"], fields["nonce_str"], fields["signature"]
    sign_str = f"POST\n/v3/pay/transactions/native\n{ts}\n{nonce}\n{{\"a\":1}}\n"
    # 不抛即签名正确
    merchant_pub.verify(
        base64.b64decode(sig_b64),
        sign_str.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_build_authorization_requires_private_key():
    gw = _make_gateway()
    gw.mch_private_key = None
    with pytest.raises(RuntimeError, match="缺商户私钥"):
        gw._build_authorization("GET", "/x", "")


# ── pay：e2e + 请求体 + 验签 ─────────────────────────────────

@pytest.mark.asyncio
async def test_pay_parses_code_url_and_verifies(monkeypatch):
    gw = _make_gateway(with_cert=True)
    body_bytes = json.dumps({"code_url": "weixin://wxpay/bizpayurl?pr=abc"}).encode()
    resp = _signed_response(200, body_bytes)
    captured = {}

    async def fake_request(method, url_path, body_str=""):
        captured.update(method=method, path=url_path, body=body_str)
        return resp

    monkeypatch.setattr(gw, "_request", fake_request)
    result = await gw.pay(99, 1.00, "测试商品")

    assert result.success is True
    assert "weixin://wxpay/bizpayurl?pr=abc" in result.transaction_id
    # 请求体字段
    req = json.loads(captured["body"])
    assert captured["method"] == "POST"
    assert captured["path"] == "/v3/pay/transactions/native"
    assert req["appid"] == "wxAPPID"
    assert req["mchid"] == "1234567890"
    assert req["out_trade_no"] == "99"
    assert req["notify_url"] == "https://example.com/notify"
    assert req["amount"] == {"total": 100, "currency": "CNY"}
    assert req["description"] == "测试商品"


@pytest.mark.asyncio
async def test_pay_rejects_bad_signature(monkeypatch):
    """应答签名被篡改 → pay raise（fail-closed，平台证书已加载时）。"""
    gw = _make_gateway(with_cert=True)
    resp = _signed_response(200, json.dumps({"code_url": "x"}).encode())
    resp.headers["Wechatpay-Signature"] = base64.b64encode(b"b" * 256).decode()
    monkeypatch.setattr(gw, "_request", _async_const(resp))
    with pytest.raises(RuntimeError, match="验签失败"):
        await gw.pay(1, 1.00)


@pytest.mark.asyncio
async def test_pay_non_200_returns_failure(monkeypatch):
    gw = _make_gateway(with_cert=True)
    resp = httpx.Response(400, content=b'{"code":"PARAM_ERROR"}')
    monkeypatch.setattr(gw, "_request", _async_const(resp))
    result = await gw.pay(1, 1.00)
    assert result.success is False
    assert "HTTP 400" in result.message


# ── query ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_trade_state_success(monkeypatch):
    gw = _make_gateway(with_cert=True)
    body = json.dumps({"trade_state": "SUCCESS", "transaction_id": "wx-txn-1"}).encode()
    monkeypatch.setattr(gw, "_request", _async_const(_signed_response(200, body)))
    result = await gw.query(99)
    assert result.success is True
    assert result.transaction_id == "wx-txn-1"
    assert result.message == "trade_state=SUCCESS"


@pytest.mark.asyncio
async def test_query_trade_state_not_pay(monkeypatch):
    gw = _make_gateway(with_cert=True)
    body = json.dumps({"trade_state": "NOTPAY"}).encode()
    monkeypatch.setattr(gw, "_request", _async_const(_signed_response(200, body)))
    result = await gw.query(99)
    assert result.success is False
    assert result.message == "trade_state=NOTPAY"


# ── refund ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refund_body_and_processing(monkeypatch):
    gw = _make_gateway(with_cert=True)
    body = json.dumps({"status": "PROCESSING", "refund_id": "wx-ref-1"}).encode()
    captured = {}

    async def fake_request(method, url_path, body_str=""):
        captured.update(method=method, path=url_path, body=body_str)
        return _signed_response(200, body)

    monkeypatch.setattr(gw, "_request", fake_request)
    result = await gw.refund(99, "wx-txn-1", 2.50)
    assert result.success is True  # PROCESSING 视为发起成功
    assert result.transaction_id == "wx-ref-1"
    req = json.loads(captured["body"])
    assert req["out_trade_no"] == "99"
    assert req["amount"]["refund"] == 250
    assert req["amount"]["total"] == 250
    assert captured["path"] == "/v3/refund/domestic/refunds"


@pytest.mark.asyncio
async def test_refund_requires_amount(monkeypatch):
    gw = _make_gateway(with_cert=True)
    result = await gw.refund(99, "wx-txn-1", None)
    assert result.success is False


# ── 无平台证书时验签跳过（dev/mock 路径）──────────────────────

@pytest.mark.asyncio
async def test_verify_response_skipped_when_no_cert(monkeypatch):
    gw = _make_gateway(with_cert=False)  # cert_map 空
    assert gw._cert_map == {}
    resp = httpx.Response(200, content=b"x", headers={})  # 无签名头
    monkeypatch.setattr(gw, "_request", _async_const(resp))
    # 无证书 → _verify_response 跳过，不 raise；pay 正常解析（body 非 JSON 会抛，用 code_url）
    body = json.dumps({"code_url": "weixin://x"}).encode()
    monkeypatch.setattr(gw, "_request", _async_const(httpx.Response(200, content=body)))
    result = await gw.pay(1, 1.00)
    assert result.success is True


# ── helpers ───────────────────────────────────────────────────

def _async_const(resp):
    async def _fake(*args, **kwargs):
        return resp
    return _fake
