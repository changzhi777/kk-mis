"""WechatPayV3Gateway 单测（P0 Day 2 骨架）

不依赖微信真证书：自签 RSA keypair 模拟平台证书验签，自造 AES-GCM 密文测解密。
覆盖：验签成功/失败、时间窗、解密、parse_notify 端到端、api_v3_key 长度校验。
真下单/退款/查单 NotImplementedError 不在此测（待密钥端到端）。
"""
import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.wechat_pay import WechatNotify, WechatPayV3Gateway

_API_V3_KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes


@pytest.fixture
def gw():
    """自签 RSA keypair（私钥签名模拟微信，公钥给网关验签）。"""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = private.public_key()
    g = WechatPayV3Gateway(_API_V3_KEY, pub, tolerance_seconds=300)
    return g, private


def _sign(private, msg: bytes) -> str:
    return base64.b64encode(
        private.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    ).decode()


def _encrypt_resource(plain: dict) -> dict:
    nonce = b"0123456789ab"  # 12 bytes
    ct = AESGCM(_API_V3_KEY).encrypt(nonce, json.dumps(plain).encode(), b"")
    return {
        "nonce": nonce.decode(),
        "ciphertext": base64.b64encode(ct).decode(),
        "associated_data": "",
    }


def test_api_v3_key_length_validation():
    with pytest.raises(ValueError):
        WechatPayV3Gateway(b"tooshort", None)


def test_verify_signature_ok(gw):
    g, private = gw
    body = b'{"id":"evt1"}'
    ts, nonce = str(int(time.time())), "n1"
    sig = _sign(private, f"{ts}\n{nonce}\n".encode() + body + b"\n")
    assert g.verify_signature(ts, nonce, body, sig) is True


def test_verify_signature_bad(gw):
    g, _ = gw
    assert g.verify_signature("t", "n", b"body", "badsig==") is False


def test_check_timestamp_window(gw):
    g, _ = gw
    now = int(time.time())
    assert g.check_timestamp(str(now), now) is True
    assert g.check_timestamp(str(now), now + 1000) is False  # 超 300s 窗
    assert g.check_timestamp("not-a-number", now) is False


def test_decrypt_resource(gw):
    g, _ = gw
    plain = {"transaction_id": "wx_txn_1", "out_trade_no": "123", "amount": {"total": 10000}}
    decrypted = g.decrypt_resource(_encrypt_resource(plain))
    assert decrypted["transaction_id"] == "wx_txn_1"
    assert decrypted["amount"]["total"] == 10000


def test_parse_notify_e2e_ok(gw):
    g, private = gw
    plain = {"transaction_id": "wx_txn_2", "out_trade_no": "42", "amount": {"total": 20000}}
    body = json.dumps({"id": "evt", "resource": _encrypt_resource(plain)}).encode()
    ts, nonce = str(int(time.time())), "n2"
    sig = _sign(private, f"{ts}\n{nonce}\n".encode() + body + b"\n")
    notify = g.parse_notify(ts, nonce, body, sig)
    assert isinstance(notify, WechatNotify)
    assert notify.transaction_id == "wx_txn_2"
    assert notify.out_trade_no == "42"
    assert notify.amount_total_fen == 20000


def test_parse_notify_bad_signature_returns_none(gw):
    g, private = gw
    plain = {"transaction_id": "x", "amount": {"total": 1}}
    body = json.dumps({"resource": _encrypt_resource(plain)}).encode()
    ts, nonce = str(int(time.time())), "n3"
    # 用错误的 signature
    assert g.parse_notify(ts, nonce, body, "YmFkc2ln==") is None


def test_pay_refund_query_raise_without_merchant_key(gw):
    """无商户私钥时 pay/refund/query 调签名链 → RuntimeError（P0 #5 代码侧已实现，真连待密钥）。

    旧桩抛 NotImplementedError；P0 Day 2.5 实装真 V3 签名后改为"缺商户私钥"
    RuntimeError。端到端下单/退款/查单的签名/验签/解析逻辑见
    test_wechat_pay_native.py（自签 RSA + 自签平台证书，无商户密钥亦覆盖）。
    """
    g, _ = gw
    g.mch_private_key = None  # 显式保证无商户私钥（dev/test gw 默认即空）
    import asyncio
    with pytest.raises(RuntimeError, match="缺商户私钥"):
        asyncio.run(g.pay(1, 100))
    with pytest.raises(RuntimeError, match="缺商户私钥"):
        asyncio.run(g.query(1))
    with pytest.raises(RuntimeError, match="缺商户私钥"):
        asyncio.run(g.refund(1, "txn", 10))
