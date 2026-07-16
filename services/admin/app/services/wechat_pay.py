"""微信支付 v3 网关（P0 Day 2 骨架，2026-07-15）

⚠️ 端到端验证待商户密钥（MCH_ID/APP_ID/API_V3_KEY/平台证书/商户私钥）到位。

本模块用 cryptography **直接实现验签（RSA-SHA256）+ 解密（AES-256-GCM）**，不黑盒
依赖 wechatpayv3 SDK——这样可用自签 RSA + 自造密文 fixture 单测验签/解密逻辑。
真下单/退款/查单调 wechatpayv3 SDK（需真商户证书），此处占位 NotImplementedError。

=== P0 Day 2 缺口 #2 修复（2026-07-15）：X.509 平台证书 + Wechatpay-Serial 校验 ===

微信回调规范：
- 验签消息串 `timestamp\\nnonce\\nbody\\n`，RSA-SHA256，用微信平台证书公钥；
- 平台证书是**真正的 X.509 证书**（`-----BEGIN CERTIFICATE-----`），不能用
  `load_pem_public_key()`（仅解析 PEM 公钥，非证书）；
- 回调带 `Wechatpay-Serial` 头，含当前回调签名所用证书的序列号——微信每隔 5 年
  轮换一次证书，回调必须根据 serial 选证书公钥验签，否则轮换期验签失败或攻击者
  伪造。

支持 3 种证书加载方式（priority）：
  1. `platform_certs` dict：`{serial: path}`，推荐生产（多证书并存期）
  2. `platform_cert_dir` str：目录扫描所有 `.pem`/`.crt`（自动找 serial）
  3. `platform_cert_path` str：单个证书（dev/测试，serial 自动归一化）
resource 用 API v3 key（32 字节）AES-256-GCM 解密，aad = associated_data。
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import Settings, settings as _global_settings
from .payment import PaymentResult


# ---------------------------------------------------------------------------
# Cert helpers — X.509 加载 + 序列号归一化
# ---------------------------------------------------------------------------

def _load_platform_cert(path: str) -> x509.Certificate:
    """从 PEM 文件加载微信支付平台证书（X.509）。

    Raises:
        RuntimeError: 加载失败（PEM 格式错误、文件不存在、非证书等）。
    """
    try:
        with open(path, "rb") as f:
            cert_data = f.read()
        return x509.load_pem_x509_certificate(cert_data, default_backend())
    except Exception as e:
        raise RuntimeError(f"Failed to load platform cert {path}: {e}") from e


def _extract_public_key(cert: x509.Certificate):
    """从 X.509 证书提取公钥（cryptography RSAPublicKey 等）。"""
    return cert.public_key()


def _normalize_serial(cert: x509.Certificate) -> str:
    """证书序列号归一化为 Wechatpay-Serial 头格式（大写 HEX，无前缀）。

    cryptography≥42 返回 int；旧版本返回 bytes；两种都安全序列化。
    """
    sn = cert.serial_number
    if isinstance(sn, int):
        return format(sn, "X")
    if isinstance(sn, (bytes, bytearray)):
        return sn.hex().upper()
    return str(sn).upper()


def _scan_cert_dir(dir_path: str) -> dict[str, x509.Certificate]:
    """扫描目录下所有 `.pem`/`.crt` 文件，按文件名排列加载为 `{serial: cert}`。

    Raises:
        ValueError: 目录不存在或无证书。
    """
    if not os.path.isdir(dir_path):
        raise ValueError(f"Cert dir not found: {dir_path}")
    result: dict[str, x509.Certificate] = {}
    for fn in sorted(os.listdir(dir_path)):
        if not (fn.endswith(".pem") or fn.endswith(".crt")):
            continue
        cert = _load_platform_cert(os.path.join(dir_path, fn))
        serial = _normalize_serial(cert)
        if serial in result:
            # 同一 serial 多文件，文件名前缀（WeChat 下载命名通常是
            # `<serial>.pem`），但同名会冲突→追加文件名前缀
            serial = f"{fn}:{serial}"
        result[serial] = cert
    if not result:
        raise ValueError(f"No .pem/.crt certificates found in {dir_path}")
    return result


@dataclass
class WechatNotify:
    """验签 + 解密后的微信支付通知（供 confirm_payment 消费）。"""

    transaction_id: str
    out_trade_no: str  # 商户订单号（映射到 ProductOrder.id）
    amount_total_fen: int  # 实付金额（分）
    resource: dict[str, Any]  # 解密后的完整 resource


class WechatPayV3Gateway:
    """微信支付 v3 网关。

    验签/解密可直接单测（注入平台公钥 + api_v3_key 或 X.509 证书集）；下单/退款
    /查单需真商户证书。

    Args:
        api_v3_key: 32 字节 AES-256 密钥。
        platform_public_key: ⚠️ 已加载的公钥（legacy 兼容位参，仅供旧单测）。
            生产请改用 `platform_certs` / `platform_cert_dir` / `platform_cert_path`。
        tolerance_seconds: 回调时间窗（防重放，默认 300s）。
        platform_certs: {serial: cert_path} 字典（生产多证书推荐）。
        platform_cert_dir: 证书目录路径（自动扫描 `.pem`/`.crt`）。
        platform_cert_path: 单个证书路径（dev/测试）。
        mch_id / app_id / mch_private_key / mch_serial_no / notify_url:
            真下单参数（端到端待密钥，详见 .env.example）。
    """

    def __init__(
        self,
        api_v3_key: bytes,
        platform_public_key: Any = None,  # legacy 兼容（pos[1]）
        tolerance_seconds: int = 300,
        *,
        platform_certs: dict[str, str] | None = None,
        platform_cert_dir: str | None = None,
        platform_cert_path: str | None = None,
        mch_id: str = "",
        app_id: str = "",
        mch_private_key: Any = None,
        mch_serial_no: str = "",
        notify_url: str = "",
    ):
        if len(api_v3_key) != 32:
            raise ValueError("API v3 key 必须 32 字节（AES-256）")
        self.api_v3_key = api_v3_key
        self.tolerance_seconds = tolerance_seconds
        self.mch_id = mch_id
        self.app_id = app_id
        self.mch_private_key = mch_private_key
        self.mch_serial_no = mch_serial_no
        self.notify_url = notify_url

        # Cert map: serial (str, upper-HEX) → x509.Certificate
        self._cert_map: dict[str, x509.Certificate] = {}
        if platform_certs:
            for serial, path in platform_certs.items():
                self._cert_map[serial.upper()] = _load_platform_cert(path)
        elif platform_cert_dir:
            self._cert_map.update(_scan_cert_dir(platform_cert_dir))
        elif platform_cert_path:
            cert = _load_platform_cert(platform_cert_path)
            self._cert_map[_normalize_serial(cert)] = cert

        # Legacy key（不附 serial），用于旧调用方（test_wechat_pay.py 用）
        self._legacy_public_key = platform_public_key

    @classmethod
    def from_settings(cls, settings: Settings = _global_settings) -> "WechatPayV3Gateway":
        """从 settings 构造（生产用）。

        Cert 加载优先级（依 settings 可选字段）：
          1. `wechat_pay_platform_certs`：`"SERIAL1:/path1.pem,SERIAL2:/path2.pem"`
          2. `wechat_pay_platform_cert_dir`：目录扫描
          3. `wechat_pay_platform_cert_path`：单个证书（dev）
        """
        api_v3_key = settings.wechat_pay_api_v3_key.encode()

        platform_certs: dict[str, str] | None = None
        platform_cert_dir: str | None = None
        platform_cert_path: str | None = None

        # 可选多证书配置（向后兼容：未设置时退回老 `platform_cert_path`）
        plat_certs_str = getattr(
            settings, "wechat_pay_platform_certs", ""
        ) or ""
        plat_dir = getattr(
            settings, "wechat_pay_platform_cert_dir", ""
        ) or ""

        if plat_certs_str:
            platform_certs = {}
            for entry in plat_certs_str.split(","):
                entry = entry.strip()
                if not entry or ":" not in entry:
                    continue
                serial, path = entry.split(":", 1)
                serial, path = serial.strip(), path.strip()
                if serial and path:
                    platform_certs[serial] = path
        elif plat_dir:
            platform_cert_dir = plat_dir
        else:
            platform_cert_path = settings.wechat_pay_platform_cert_path

        mch_key = None
        if settings.wechat_pay_mch_private_key_path:
            with open(settings.wechat_pay_mch_private_key_path, "rb") as f:
                mch_key = serialization.load_pem_private_key(f.read(), password=None)

        return cls(
            api_v3_key=api_v3_key,
            platform_certs=platform_certs,
            platform_cert_dir=platform_cert_dir,
            platform_cert_path=platform_cert_path,
            tolerance_seconds=settings.payment_signature_tolerance_seconds,
            mch_id=settings.wechat_pay_mch_id,
            app_id=settings.wechat_pay_app_id,
            mch_private_key=mch_key,
            notify_url=settings.wechat_pay_notify_url,
        )

    # ── Cert helpers（暴露给应用层做轮换监控）────────────
    def list_cert_serials(self) -> list[str]:
        """返回当前 cert map 的所有 serial（upper-HEX，含 legacy 时额外返回 ['_legacy']）。"""
        if self._legacy_public_key is not None:
            return list(self._cert_map.keys()) + ["_legacy"]
        return list(self._cert_map.keys())

    def has_cert_for_serial(self, serial: str) -> bool:
        """给定 Wechatpay-Serial 头是否能找到证书。"""
        return (serial or "").upper() in self._cert_map

    # ── 验签（cert map 模式 + Wechatpay-Serial）────────────
    def _cert_by_serial(self, serial: str) -> x509.Certificate:
        """按 serial 取证书；找不到 raise ValueError（应用层决定→401 还是 retry）。"""
        cert = self._cert_map.get((serial or "").upper())
        if cert is None:
            raise ValueError(f"Unknown platform cert serial: {serial}")
        return cert

    def verify_callback(self, headers: dict, body: bytes) -> bool:
        """验签微信 v3 回调，根据 `Wechatpay-Serial` 头选平台证书。

        Headers 必须含：Wechatpay-Serial / Wechatpay-Timestamp / Wechatpay-Nonce
        / Wechatpay-Signature。任一缺失、时间窗越界、serial 未知或签名错→返回 False。
        """
        def _h(name: str) -> str:
            # 大小写不敏感（HTTP 头在某些代理会被规范化）
            for k, v in headers.items():
                if k.lower() == name.lower():
                    return (v or "").strip()
            return ""

        serial = _h("Wechatpay-Serial")
        timestamp = _h("Wechatpay-Timestamp")
        nonce = _h("Wechatpay-Nonce")
        signature = _h("Wechatpay-Signature")

        if not (serial and timestamp and nonce and signature):
            return False
        if not self.check_timestamp(timestamp):
            return False

        try:
            cert = self._cert_by_serial(serial)
        except ValueError:
            return False

        public_key = _extract_public_key(cert)
        msg = f"{timestamp}\n{nonce}\n".encode() + body + b"\n"
        try:
            sig = base64.b64decode(signature, validate=True)
            public_key.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False

    # ── 验签（legacy / 单证书）─────────────────────
    def verify_signature(
        self, timestamp: str, nonce: str, body: bytes, signature_b64: str
    ) -> bool:
        """RSA-SHA256 验签。

        优先取 legacy `platform_public_key`（旧测试用）；否则取 cert map
        第一项证书的公钥。验签消息 = `timestamp\\nnonce\\nbody\\n`。
        """
        if self._legacy_public_key is not None:
            pub = self._legacy_public_key
        else:
            if not self._cert_map:
                return False
            pub = _extract_public_key(next(iter(self._cert_map.values())))
        msg = f"{timestamp}\n{nonce}\n".encode() + body + b"\n"
        try:
            sig = base64.b64decode(signature_b64, validate=True)
            pub.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
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

    # ── 解密 ──────────────────────────────────────────────
    def decrypt_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        """AES-256-GCM 解密 resource.ciphertext → 原始 JSON dict。"""
        nonce = resource["nonce"].encode()
        ciphertext = base64.b64decode(resource["ciphertext"])
        associated = resource.get("associated_data", "").encode()
        plain = AESGCM(self.api_v3_key).decrypt(nonce, ciphertext, associated)
        return json.loads(plain)

    # ── 端到端：验签 → 时间窗 → 解密 ─────────────────────
    def parse_notify(
        self, timestamp: str, nonce: str, body: bytes, signature_b64: str
    ) -> WechatNotify | None:
        """完整解析微信回调（legacy 接口，验签走单证书或 legacy key）；任一步失败返回 None。"""
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

    # ── 下单/退款/查单（需真商户证书，端到端待密钥）──────
    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult:
        """Native 统一下单（TODO：真商户证书；成功返回 code_url 于 message）。"""
        raise NotImplementedError("WechatPayV3Gateway.pay 需真商户证书，端到端待密钥")

    async def refund(self, order_id: int, transaction_id: str, amount=None) -> PaymentResult:
        raise NotImplementedError("WechatPayV3Gateway.refund 端到端待密钥")

    async def query(self, order_id: int, transaction_id: str = "") -> PaymentResult:
        raise NotImplementedError("WechatPayV3Gateway.query 端到端待密钥")
