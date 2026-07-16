"""payments notify 路由级回调测试（P0 Day 2 缺口 #3 修复，2026-07-15）

覆盖：
  1) test_notify_success             — 完整合法回调 → 200 + SUCCESS
  2) test_notify_missing_signature   — 缺 Wechatpay-Signature → 401
  3) test_notify_invalid_signature   — 错误签名 → 401
  4) test_notify_invalid_json        — body 不是 JSON → 400
  5) test_notify_missing_field       — body 缺顶层 id → 400
  6) test_notify_invalid_resource    — resource 缺 ciphertext → 400
  7) test_notify_decrypt_failed      — ciphertext 是垃圾 → 400
  8) test_notify_unknown_gateway     — gateway_name=foo → 200 SUCCESS ignored
  9) test_notify_idempotent_replay   — 同 body 重复 POST → 都 200 SUCCESS（幂等 ACK）
  10) test_notify_redis_replay_409   — 同 timestamp+nonce 不同 body → 第二次 409

自签 RSA keypair 模拟平台证书验签；自造 AES-GCM 密文测解密；
FastAPI TestClient + conftest.session client 模拟完整 HTTP POST。
Redis 重放测试 patch app.cache._client 注入轻量 FakeRedis（NX 语义）。
"""
import base64
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app import cache

_API_V3_KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes


# ── 测试 fixtures：自签 RSA keypair + 自签 X.509 证书 + 测试网关 ──────────


def _make_self_signed_cert(private_key, common_name: str = "Test WeChat Platform"):
    """从 RSA 私钥生成自签 X.509 证书（PEM bytes）。"""
    subject = issuer = x509.Name(
        [x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, common_name)]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


@pytest.fixture(scope="module")
def test_keys():
    """自签 RSA keypair + 自签 X.509 证书 + 构造 WechatPayV3Gateway（cert map 模式）。

    用 platform_cert_path 让 verify_callback 走 _cert_by_serial() → _extract_public_key()
    → RSA-SHA256 验签的完整路径，与生产 wechat 平台证书路径一致。
    """
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert_pem = _make_self_signed_cert(private)

    # 写入临时 PEM 文件（verify_callback 走 cert_map）
    fd, cert_path = tempfile.mkstemp(suffix=".pem", prefix="wxpay_test_cert_")
    os.close(fd)
    with open(cert_path, "wb") as f:
        f.write(cert_pem)

    from app.services.wechat_pay import WechatPayV3Gateway

    gw = WechatPayV3Gateway(
        _API_V3_KEY,
        tolerance_seconds=300,
        platform_cert_path=cert_path,
    )
    # 提取 cert serial 用于签名 header
    cert_obj = x509.load_pem_x509_certificate(cert_pem)
    serial = format(cert_obj.serial_number, "X")
    yield private, gw, serial, cert_path

    # cleanup
    try:
        os.unlink(cert_path)
    except OSError:
        pass


def _sign(private, msg: bytes) -> str:
    return base64.b64encode(
        private.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    ).decode()


def _encrypt_resource(plain: dict) -> dict:
    """AES-256-GCM 加密 plain dict → resource 三件套（与 test_wechat_pay 一致）。"""
    nonce = b"0123456789ab"  # 12 bytes
    ct = AESGCM(_API_V3_KEY).encrypt(nonce, json.dumps(plain).encode(), b"")
    return {
        "nonce": nonce.decode(),
        "ciphertext": base64.b64encode(ct).decode(),
        "associated_data": "",
    }


def _build_notify_body(
    *, transaction_id: str = "wx_txn_default", out_trade_no: str = "1", total: int = 10000
) -> bytes:
    """构造合法回调 body（含 4 顶层必填字段 + AES 加密 resource）。"""
    resource = _encrypt_resource(
        {
            "transaction_id": transaction_id,
            "out_trade_no": out_trade_no,
            "amount": {"total": total, "currency": "CNY"},
        }
    )
    return json.dumps(
        {
            "id": f"evt_{transaction_id}_{int(time.time()*1000)}",
            "create_time": str(int(time.time())),
            "resource_type": "encrypt-resource",
            "event_type": "TRANSACTION.SUCCESS",
            "resource": resource,
        }
    ).encode()


def _build_signed_headers(
    private, body: bytes, *, timestamp=None, nonce: str = "n_default", serial: str = ""
) -> dict:
    """构造 4 个微信回调 header（签名用 private 钥签）。

    包含 Wechatpay-Serial（verify_callback 用 serial 在 cert_map 中查证书）。
    """
    ts = str(timestamp if timestamp is not None else int(time.time()))
    sig = _sign(private, f"{ts}\n{nonce}\n".encode() + body + b"\n")
    headers = {
        "Wechatpay-Timestamp": ts,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": sig,
    }
    if serial:
        headers["Wechatpay-Serial"] = serial
    return headers


class FakeRedis:
    """轻量 Redis mock：仅支持 set(k, v, nx, ex) NX 语义（重放检测用）。"""

    def __init__(self):
        self.store: set[str] = set()
        self.set_log: list[tuple[str, bool]] = []  # (key, ok) 审计

    async def set(self, key, value, nx=False, ex=0):
        if nx and key in self.store:
            self.set_log.append((key, False))
            return None  # 已存在 → NX 拒绝（重放）
        self.store.add(key)
        self.set_log.append((key, True))
        return True


@pytest.fixture
def patched_payments_route(test_keys):
    """返回 (private, serial) + patch WechatPayV3Gateway.from_settings + run_issue_task_async。

    Note: 不在 fixture 内 patch cache._client（仅 redis_replay_409 测试需要）。
    """
    private, gw, serial, _cert_path = test_keys
    with patch(
        "app.routes.cms.payments.WechatPayV3Gateway.from_settings", return_value=gw
    ), patch(
        "app.routes.cms.payments.run_issue_task_async", new=AsyncMock(return_value=None)
    ) as _run_mock:
        yield private, serial


# ── 10 项路由级回调测试 ──────────────────────────────────────────────


def test_notify_success(client, patched_payments_route):
    """完整合法回调 → 200 + SUCCESS（订单不存在 → PaymentConflictError → ACK 200）。

    ACK 防微信重试风暴：订单不存在时仍回 200 SUCCESS，但不入队发卡（待人工排查）。
    """
    private, serial = patched_payments_route
    body = _build_notify_body(
        transaction_id="wx_t_success", out_trade_no="999999", total=10000
    )
    headers = _build_signed_headers(private, body, serial=serial)
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    body_json = r.json()
    assert body_json["code"] == "SUCCESS"
    assert body_json["message"] == "OK"


def test_notify_missing_signature_header(client, patched_payments_route):
    """缺 Wechatpay-Signature → 401（verify_callback 返回 False → SignatureError）。"""
    _private, serial = patched_payments_route
    body = _build_notify_body(transaction_id="wx_t_nosig")
    headers = {
        "Wechatpay-Timestamp": str(int(time.time())),
        "Wechatpay-Nonce": "n",
        "Wechatpay-Serial": serial,
        # 故意缺 Wechatpay-Signature
    }
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 401
    assert "signature" in r.json()["detail"].lower()


def test_notify_invalid_signature(client, patched_payments_route):
    """错误签名 → 401（verify_signature 解 base64 + RSA verify 抛 InvalidSignature）。"""
    _private, serial = patched_payments_route
    body = _build_notify_body(transaction_id="wx_t_badsig")
    ts = str(int(time.time()))
    headers = {
        "Wechatpay-Timestamp": ts,
        "Wechatpay-Nonce": "n_badsig",
        "Wechatpay-Serial": serial,
        "Wechatpay-Signature": base64.b64encode(b"definitely-not-a-real-sig").decode(),
    }
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 401


def test_notify_invalid_json(client, patched_payments_route):
    """body 不是 JSON → 400（json.JSONDecodeError → WechatNotifyInvalidJSONError）。"""
    private, serial = patched_payments_route
    body = b"this is definitely not json {"
    headers = _build_signed_headers(private, body, nonce="n_badjson", serial=serial)
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 400
    assert "json" in r.json()["detail"].lower() or "parse_notify" in r.json()["detail"]


def test_notify_missing_field(client, patched_payments_route):
    """body 缺顶层 id → 400（WechatNotifyMissingFieldError）。"""
    private, serial = patched_payments_route
    # 顶层只有 create_time/resource_type/resource，故意缺 id
    body = json.dumps(
        {
            "create_time": str(int(time.time())),
            "resource_type": "encrypt-resource",
            "resource": {
                "ciphertext": "x",
                "nonce": "x",
                "associated_data": "",
            },
        }
    ).encode()
    headers = _build_signed_headers(private, body, nonce="n_miss", serial=serial)
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "missing" in detail.lower() or "parse_notify" in detail


def test_notify_invalid_resource(client, patched_payments_route):
    """resource 缺 ciphertext → 400（WechatNotifyInvalidResourceError）。"""
    private, serial = patched_payments_route
    body = json.dumps(
        {
            "id": "evt_x",
            "create_time": str(int(time.time())),
            "resource_type": "encrypt-resource",
            "resource": {
                # 故意缺 ciphertext
                "nonce": "n",
                "associated_data": "",
            },
        }
    ).encode()
    headers = _build_signed_headers(private, body, nonce="n_badres", serial=serial)
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "resource" in detail.lower() or "missing" in detail.lower()


def test_notify_decrypt_failed(client, patched_payments_route):
    """ciphertext 是垃圾 → 400（cryptography InvalidTag → WechatNotifyDecryptError）。"""
    private, serial = patched_payments_route
    body = json.dumps(
        {
            "id": "evt_y",
            "create_time": str(int(time.time())),
            "resource_type": "encrypt-resource",
            "resource": {
                "ciphertext": base64.b64encode(b"\x00" * 64).decode(),
                "nonce": "MTIzNDU2Nzg5MGE=",  # "1234567890a" base64
                "associated_data": "",
            },
        }
    ).encode()
    headers = _build_signed_headers(private, body, nonce="n_decrypt", serial=serial)
    r = client.post(
        "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "decrypt" in detail.lower() or "aes" in detail.lower()


def test_notify_unknown_gateway(client, patched_payments_route):
    """gateway_name=alipay → 200 SUCCESS ignored（mock 路径，忽略其他 gateway）。

    保持路由设计：未知 gateway 名走 ignored 200，不暴露路由存在性。
    """
    r = client.post(
        "/admin/api/v1/cms/payments/notify/alipay", content=b'{"any":"json"}'
    )
    assert r.status_code == 200
    body_json = r.json()
    assert body_json["code"] == "SUCCESS"
    assert body_json["message"] == "ignored"


def test_notify_idempotent_replay(client, patched_payments_route):
    """同 body 重复 POST → 都 200 SUCCESS（幂等 ACK，订单不存在 → PaymentConflictError）。

    注：路由的 `_check_replay` 用 timestamp+nonce 做 Redis NX 拦截重放。Redis 可用时
    同 ts+nonce 第二次会被 Redis 检测为重放 409；为测试**业务幂等性**（支付事实层），
    本测试 patch cache._client = None 强制 fail-open，让两次都到 confirm_payment。
    业务幂等表现：订单不存在 → PaymentConflictError → ACK 200 SUCCESS（防重试风暴）。
    """
    private, serial = patched_payments_route
    body = _build_notify_body(
        transaction_id="wx_t_idem", out_trade_no="88888", total=5000
    )
    headers = _build_signed_headers(private, body, nonce="n_idem_same", serial=serial)

    with patch.object(cache, "_client", None):  # 强制 Redis fail-open
        r1 = client.post(
            "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
        )
        r2 = client.post(
            "/admin/api/v1/cms/payments/notify/wechat", content=body, headers=headers
        )

    # 两次都到 parse_notify_safe + confirm_payment
    # 订单 88888 不存在 → PaymentConflictError → ACK 200 SUCCESS（防重试风暴）
    assert r1.status_code == 200, f"first: {r1.status_code} {r1.text}"
    assert r1.json()["code"] == "SUCCESS"
    assert r2.status_code == 200, f"second: {r2.status_code} {r2.text}"
    assert r2.json()["code"] == "SUCCESS"


def test_notify_redis_replay_409(client, patched_payments_route):
    """同 timestamp+nonce 不同 body → 第二次 409（Redis NX 检测）。

    patch app.cache._client 为 FakeRedis（NX 语义）：
      - 第一次：NX 成功 → 不重放 → 走正常路径
      - 第二次：NX 失败（key 已存在）→ WechatNotifyReplayError → 409
    """
    private, serial = patched_payments_route
    fake_redis = FakeRedis()

    # 共享 timestamp+nonce 但 transaction_id 不同 → 同重放键
    shared_ts = str(int(time.time()))
    shared_nonce = "n_redis_replay"

    body1 = _build_notify_body(transaction_id="wx_t_replay_a", out_trade_no="77777")
    body2 = _build_notify_body(transaction_id="wx_t_replay_b", out_trade_no="66666")
    headers1 = _build_signed_headers(
        private, body1, timestamp=shared_ts, nonce=shared_nonce, serial=serial
    )
    headers2 = _build_signed_headers(
        private, body2, timestamp=shared_ts, nonce=shared_nonce, serial=serial
    )

    with patch.object(cache, "_client", fake_redis):
        # 第一次：NX 成功 → 走正常路径（订单不存在 → ACK 200 SUCCESS）
        r1 = client.post(
            "/admin/api/v1/cms/payments/notify/wechat", content=body1, headers=headers1
        )
        assert r1.status_code == 200, f"first: {r1.status_code} {r1.text}"
        assert r1.json()["code"] == "SUCCESS"

        # 第二次：Redis NX 失败 → 重放 → 409
        r2 = client.post(
            "/admin/api/v1/cms/payments/notify/wechat", content=body2, headers=headers2
        )
        assert r2.status_code == 409, f"second: {r2.status_code} {r2.text}"
        assert r2.json()["detail"] == "replay"

    # 校验 Redis 记录：2 次调用，1 次成功 1 次失败
    assert len(fake_redis.set_log) == 2
    assert fake_redis.set_log[0][1] is True  # 第一次 OK
    assert fake_redis.set_log[1][1] is False  # 第二次 NX 失败（重放）
    # 重放键应为 wxpay:replay:{ts}:{nonce}
    expected_key = f"wxpay:replay:{shared_ts}:{shared_nonce}"
    assert fake_redis.set_log[0][0] == expected_key
    assert fake_redis.set_log[1][0] == expected_key