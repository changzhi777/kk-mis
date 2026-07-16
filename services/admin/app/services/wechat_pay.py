"""微信支付 v3 网关（P0 Day 2 骨架，2026-07-15）

⚠️ 端到端验证待商户密钥（MCH_ID/APP_ID/API_V3_KEY/平台证书/商户私钥）到位。

本模块用 cryptography **直接实现验签（RSA-SHA256）+ 解密（AES-256-GCM）**，不黑盒
依赖 wechatpayv3 SDK——这样可用自签 RSA + 自造密文 fixture 单测验签/解密逻辑。
真下单/退款/查单调 wechatpayv3 SDK（需真商户证书），此处占位 NotImplementedError。

微信支付 v3 回调规范：
- 验签消息串 `timestamp\\nnonce\\nbody\\n`，RSA-SHA256，用微信平台证书公钥；
- resource 用 API v3 key（32 字节）AES-256-GCM 解密，aad = associated_data。
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from ..config import Settings, settings as _global_settings
from .payment import PaymentResult


@dataclass
class WechatNotify:
    """验签 + 解密后的微信支付通知（供 confirm_payment 消费）。"""

    transaction_id: str
    out_trade_no: str  # 商户订单号（映射到 ProductOrder.id）
    amount_total_fen: int  # 实付金额（分）
    resource: dict[str, Any]  # 解密后的完整 resource


class WechatPayV3Gateway:
    """微信支付 v3 网关。

    验签/解密可直接单测（注入平台公钥 + api_v3_key）；下单/退款/查单需真商户证书。
    """

    def __init__(
        self,
        api_v3_key: bytes,
        platform_public_key: Any,
        tolerance_seconds: int = 300,
        *,
        mch_id: str = "",
        app_id: str = "",
        mch_private_key: Any = None,
        mch_serial_no: str = "",
        notify_url: str = "",
    ):
        if len(api_v3_key) != 32:
            raise ValueError("API v3 key 必须 32 字节（AES-256）")
        self.api_v3_key = api_v3_key
        self.platform_public_key = platform_public_key
        self.tolerance_seconds = tolerance_seconds
        self.mch_id = mch_id
        self.app_id = app_id
        self.mch_private_key = mch_private_key
        self.mch_serial_no = mch_serial_no
        self.notify_url = notify_url

    @classmethod
    def from_settings(cls, settings: Settings = _global_settings) -> "WechatPayV3Gateway":
        """从 settings 构造（生产用；需配齐 WECHAT_PAY_*，否则由 config fail-fast 拦截）。"""
        with open(settings.wechat_pay_platform_cert_path, "rb") as f:
            pub = load_pem_public_key(f.read())
        mch_key = None
        if settings.wechat_pay_mch_private_key_path:
            with open(settings.wechat_pay_mch_private_key_path, "rb") as f:
                mch_key = serialization.load_pem_private_key(f.read(), password=None)
        return cls(
            api_v3_key=settings.wechat_pay_api_v3_key.encode(),
            platform_public_key=pub,
            tolerance_seconds=settings.payment_signature_tolerance_seconds,
            mch_id=settings.wechat_pay_mch_id,
            app_id=settings.wechat_pay_app_id,
            mch_private_key=mch_key,
            notify_url=settings.wechat_pay_notify_url,
        )

    # ── 验签 ──────────────────────────────────────────────────────
    def verify_signature(
        self, timestamp: str, nonce: str, body: bytes, signature_b64: str
    ) -> bool:
        """RSA-SHA256 验签。验签消息 = `timestamp\\nnonce\\nbody\\n`。"""
        msg = f"{timestamp}\n{nonce}\n".encode() + body + b"\n"
        try:
            sig = base64.b64decode(signature_b64)
            self.platform_public_key.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False

    def check_timestamp(self, timestamp: str, now_ts: int | None = None) -> bool:
        """时间窗校验（防重放，默认 ±300s）。"""
        try:
            ts = int(timestamp)
        except (TypeError, ValueError):
            return False
        now = now_ts if now_ts is not None else int(time.time())
        return abs(now - ts) <= self.tolerance_seconds

    # ── 解密 ──────────────────────────────────────────────────────
    def decrypt_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        """AES-256-GCM 解密 resource.ciphertext → 原始 JSON dict。"""
        nonce = resource["nonce"].encode()
        ciphertext = base64.b64decode(resource["ciphertext"])
        associated = resource.get("associated_data", "").encode()
        plain = AESGCM(self.api_v3_key).decrypt(nonce, ciphertext, associated)
        return json.loads(plain)

    # ── 端到端：验签 → 时间窗 → 解密 ─────────────────────────────
    def parse_notify(
        self, timestamp: str, nonce: str, body: bytes, signature_b64: str
    ) -> WechatNotify | None:
        """完整解析微信回调；任一步失败返回 None（调用方回 401）。"""
        if not self.check_timestamp(timestamp):
            return None
        if not self.verify_signature(timestamp, nonce, body, signature_b64):
            return None
        event = json.loads(body)
        resource = self.decrypt_resource(event["resource"])
        amount = resource.get("amount", {}) or {}
        return WechatNotify(
            transaction_id=str(resource.get("transaction_id", "")),
            out_trade_no=str(resource.get("out_trade_no", "")),
            amount_total_fen=int(amount.get("total", 0)),
            resource=resource,
        )

    # ── 下单/退款/查单（需真商户证书，端到端待密钥）──────────────
    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult:
        """Native 统一下单（TODO：真商户证书；成功返回 code_url 于 message）。"""
        raise NotImplementedError("WechatPayV3Gateway.pay 需真商户证书，端到端待密钥")

    async def refund(self, order_id: int, transaction_id: str, amount=None) -> PaymentResult:
        raise NotImplementedError("WechatPayV3Gateway.refund 端到端待密钥")

    async def query(self, order_id: int, transaction_id: str = "") -> PaymentResult:
        raise NotImplementedError("WechatPayV3Gateway.query 端到端待密钥")
