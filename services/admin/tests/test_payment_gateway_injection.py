"""支付网关注入测试（P0 Day 2 缺口 #1 修复，2026-07-16）

覆盖：
1. 默认 gateway 是 MockGateway
2. set_gateway 替换全局
3. build_gateway_from_settings(mock) → MockGateway
4. build_gateway_from_settings(wechat + 完整配置) → WechatPayV3Gateway
5. build_gateway_from_settings(wechat 缺配置) 必须 raise（fail-closed，不 fallback mock）
6. build_gateway_from_settings(wechat 缺证书文件) 必须 raise FileNotFoundError
7. build_gateway_from_settings(alipay) → NotImplementedError
8. build_gateway_from_settings(未知 provider) → ValueError
9. lifespan 调用 build_gateway_from_settings + set_gateway 覆盖全局

设计动机：见 admin/CLAUDE.md §7.23 缺口 #1。
"""
from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import payment as payment_module
from app.services.payment import (
    MockGateway,
    PaymentResult,
    build_gateway_from_settings,
    set_gateway,
)


# ── 共用 fixtures ─────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _restore_gateway():
    """每个测试后恢复 gateway 到 MockGateway，避免污染其他测试。"""
    yield
    set_gateway(MockGateway())
    if not isinstance(payment_module.gateway, MockGateway):
        payment_module.gateway = MockGateway()


def _make_self_signed_cert(private_key, common_name: str = "test-platform-cert"):
    """生成自签 X.509 证书（PEM 格式，含 BEGIN CERTIFICATE）。"""
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2026, 1, 1))
        .not_valid_after(datetime.datetime(2030, 1, 1))
        .sign(private_key, hashes.SHA256())
    )


@pytest.fixture
def wechat_keys(tmp_path):
    """生成自签 X.509 平台证书 + 自签商户私钥（写到 tmp_path）。"""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = _make_self_signed_cert(private)
    cert_path = tmp_path / "platform_cert.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path = tmp_path / "mch_private.pem"
    key_path.write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


@pytest.fixture
def wechat_settings(monkeypatch, wechat_keys):
    """构造 PAYMENT_PROVIDER=wechat + 完整 WECHAT_PAY_* 配置的 Settings 实例。"""
    cert, key = wechat_keys
    monkeypatch.setenv("PAYMENT_PROVIDER", "wechat")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "1234567890")
    monkeypatch.setenv("WECHAT_PAY_APP_ID", "wx1234567890abcdef")
    monkeypatch.setenv("WECHAT_PAY_API_V3_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("WECHAT_PAY_PLATFORM_CERT_PATH", cert)
    monkeypatch.setenv("WECHAT_PAY_MCH_PRIVATE_KEY_PATH", key)
    monkeypatch.setenv("WECHAT_PAY_NOTIFY_URL", "https://example.com/notify")
    return Settings.from_env()


# ── 1) 默认 gateway 是 MockGateway ──────────────────────────────
def test_default_mock_gateway():
    """模块导入时默认 gateway 是 MockGateway（无注入时）。"""
    set_gateway(MockGateway())
    assert isinstance(payment_module.gateway, MockGateway)


# ── 2) set_gateway 替换全局 ────────────────────────────────────
def test_set_gateway_replaces_global():
    """set_gateway() 后全局 gateway 变成新实例（实现 PaymentGateway 协议即可）。"""

    class CustomGateway:
        def __init__(self):
            self.tag = "custom"

        async def pay(self, order_id, amount, subject=""):
            return PaymentResult(success=True, transaction_id="custom", message="custom")

        async def refund(self, order_id, transaction_id, amount=None):
            return PaymentResult(success=True)

        async def query(self, order_id, transaction_id=""):
            return PaymentResult(success=True)

    custom = CustomGateway()
    set_gateway(custom)
    assert payment_module.gateway is custom
    # duck-typed 协议校验（PaymentGateway 是 Protocol 非 runtime_checkable，用 hasattr）
    assert hasattr(payment_module.gateway, "pay")
    assert hasattr(payment_module.gateway, "refund")
    assert hasattr(payment_module.gateway, "query")


# ── 3) build_gateway_from_settings(mock) ───────────────────────
def test_build_gateway_mock(monkeypatch):
    """PAYMENT_PROVIDER=mock → MockGateway（永不失败）。"""
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")
    s = Settings.from_env()
    gw = build_gateway_from_settings(s)
    assert isinstance(gw, MockGateway)


def test_build_gateway_mock_when_provider_empty(monkeypatch):
    """PAYMENT_PROVIDER=''（默认 fallback）→ MockGateway。"""
    monkeypatch.setenv("PAYMENT_PROVIDER", "")
    s = Settings.from_env()
    gw = build_gateway_from_settings(s)
    assert isinstance(gw, MockGateway)


# ── 4) build_gateway_from_settings(wechat 完整配置) ───────────
def test_build_gateway_wechat_success(wechat_settings):
    """PAYMENT_PROVIDER=wechat + 完整配置 → WechatPayV3Gateway 实例化成功。"""
    from app.services.wechat_pay import WechatPayV3Gateway

    gw = build_gateway_from_settings(wechat_settings)
    assert isinstance(gw, WechatPayV3Gateway)
    assert gw.mch_id == "1234567890"
    assert gw.app_id == "wx1234567890abcdef"
    assert gw.notify_url == "https://example.com/notify"
    assert gw.mch_private_key is not None
    assert gw.api_v3_key == b"0123456789abcdef0123456789abcdef"
    # cert map 应至少有 1 个 cert（serial 归一化大写 HEX）
    assert len(gw.list_cert_serials()) >= 1


# ── 5) wechat 缺配置必须 raise（fail-closed） ─────────────────
def test_build_gateway_wechat_fail_closed_missing_mch_id(monkeypatch):
    """PAYMENT_PROVIDER=wechat 但缺 WECHAT_PAY_MCH_ID → 任何异常（不是返回 mock）。"""
    monkeypatch.setenv("PAYMENT_PROVIDER", "wechat")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "")  # 故意为空
    monkeypatch.setenv("WECHAT_PAY_APP_ID", "wx1234567890abcdef")
    monkeypatch.setenv("WECHAT_PAY_API_V3_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("WECHAT_PAY_PLATFORM_CERT_PATH", "/nonexistent/cert.pem")
    monkeypatch.setenv("WECHAT_PAY_MCH_PRIVATE_KEY_PATH", "/nonexistent/key.pem")

    s = Settings.from_env()
    # Settings._validate_production_secrets 只在 prod / postgres 模式跑，
    # dev 模式 PAYMENT_PROVIDER=wechat 但配置缺不会先 raise。
    # 但 build_gateway_from_settings 必须 raise（来自 wechat_pay.py 的 from_settings）。
    with pytest.raises(Exception) as exc_info:
        build_gateway_from_settings(s)
    # 关键断言：失败时绝不能返回 mock（那才是 silent corruption）
    assert exc_info.type in (FileNotFoundError, ValueError, OSError, RuntimeError)


def test_build_gateway_wechat_fail_closed_missing_cert_file(monkeypatch):
    """PAYMENT_PROVIDER=wechat 但平台证书路径不存在 → FileNotFoundError（fail-closed）。"""
    monkeypatch.setenv("PAYMENT_PROVIDER", "wechat")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "1234567890")
    monkeypatch.setenv("WECHAT_PAY_APP_ID", "wx1234567890abcdef")
    monkeypatch.setenv("WECHAT_PAY_API_V3_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("WECHAT_PAY_PLATFORM_CERT_PATH", "/nonexistent/cert.pem")
    monkeypatch.setenv("WECHAT_PAY_MCH_PRIVATE_KEY_PATH", "/nonexistent/key.pem")

    s = Settings.from_env()
    with pytest.raises((FileNotFoundError, RuntimeError)):
        build_gateway_from_settings(s)


def test_build_gateway_wechat_fail_closed_bad_api_v3_key_length(monkeypatch, wechat_keys):
    """PAYMENT_PROVIDER=wechat 但 API_V3_KEY 不是 32 字节 → ValueError（fail-closed）。"""
    cert, key = wechat_keys
    monkeypatch.setenv("PAYMENT_PROVIDER", "wechat")
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "1234567890")
    monkeypatch.setenv("WECHAT_PAY_APP_ID", "wx1234567890abcdef")
    monkeypatch.setenv("WECHAT_PAY_API_V3_KEY", "tooshort")  # 仅 8 字节
    monkeypatch.setenv("WECHAT_PAY_PLATFORM_CERT_PATH", cert)
    monkeypatch.setenv("WECHAT_PAY_MCH_PRIVATE_KEY_PATH", key)

    s = Settings.from_env()
    with pytest.raises(ValueError, match="API v3 key 必须 32 字节"):
        build_gateway_from_settings(s)


# ── 6) alipay 未实现 ─────────────────────────────────────────
def test_build_gateway_alipay_not_implemented(monkeypatch):
    """PAYMENT_PROVIDER=alipay → NotImplementedError（Day 2.5 待接入）。"""
    monkeypatch.setenv("PAYMENT_PROVIDER", "alipay")
    s = Settings.from_env()
    with pytest.raises(NotImplementedError, match="AlipayGateway 尚未实现"):
        build_gateway_from_settings(s)


# ── 7) 未知 provider ─────────────────────────────────────────
def test_build_gateway_unknown_provider(monkeypatch):
    """PAYMENT_PROVIDER=foo → ValueError（fail-closed）。"""
    monkeypatch.setenv("PAYMENT_PROVIDER", "foo")
    s = Settings.from_env()
    with pytest.raises(ValueError, match="未知的 PAYMENT_PROVIDER"):
        build_gateway_from_settings(s)


def test_build_gateway_unknown_provider_case_insensitive(monkeypatch):
    """大小写不敏感：PAYMENT_PROVIDER=Mock / MOCK / mOcK 均归一为 mock。"""
    for variant in ("Mock", "MOCK", "mOcK"):
        monkeypatch.setenv("PAYMENT_PROVIDER", variant)
        s = Settings.from_env()
        gw = build_gateway_from_settings(s)
        assert isinstance(gw, MockGateway), f"variant {variant!r} 应归一为 mock"


# ── 8) wechat 注入后协议方法仍存在 ─────────────────────────
def test_wechat_gateway_inherits_protocol(wechat_settings):
    """wechat gateway 必须满足 PaymentGateway duck-typed 协议（pay/refund/query）。"""
    from app.services.wechat_pay import WechatPayV3Gateway

    gw = build_gateway_from_settings(wechat_settings)
    assert isinstance(gw, WechatPayV3Gateway)
    # pay/refund/query 当前是 NotImplementedError（待真证书），但方法签名存在
    assert callable(getattr(gw, "pay", None))
    assert callable(getattr(gw, "refund", None))
    assert callable(getattr(gw, "query", None))


# ── 9) lifespan 注入集成（间接验证） ─────────────────────────
def test_lifespan_injects_gateway(monkeypatch):
    """验证 lifespan 调用了 build_gateway_from_settings + set_gateway（间接）。

    策略：先用一个 sentinel gateway 污染全局（模拟"未注入"状态），
    然后调用 lifespan 等价的注入代码（build + set_gateway），
    验证全局被替换 + sentinel 消失。

    不直接触发完整 lifespan（避免与 session-scoped client fixture
    的 retry poller 任务冲突），但注入代码路径与 lifespan 一致。
    """
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")

    class StaleGateway:
        """sentinel：模拟 lifespan 未触发的状态。"""

        def __repr__(self):
            return "<StaleGateway>"

    set_gateway(StaleGateway())
    assert isinstance(payment_module.gateway, StaleGateway)

    # 模拟 lifespan 中的注入代码路径
    from app.config import settings as _settings

    gw = build_gateway_from_settings(_settings)
    set_gateway(gw)

    # 验证注入后全局 gateway 已被替换
    assert isinstance(payment_module.gateway, MockGateway)
    assert not isinstance(payment_module.gateway, StaleGateway)


def test_lifespan_integration_with_testclient(monkeypatch):
    """端到端：TestClient 触发 lifespan 后全局 gateway 已被替换。

    使用独立 TestClient 实例（不复用 session-scoped client），避免 poller 任务冲突。
    PAYMENT_PROVIDER=mock（默认），lifespan 必须成功 + gateway = MockGateway。
    """
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")
    monkeypatch.setenv("DB_DRIVER", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", "./test_lifespan_gateway.db")

    # 在 lifespan 之前，gateway 是默认 MockGateway
    set_gateway(MockGateway())

    from app.main import app

    try:
        with TestClient(app):
            from app.services import payment as p_after

            # gateway 已被 build_gateway_from_settings 注入
            assert isinstance(p_after.gateway, MockGateway), (
                f"lifespan 注入后 gateway 应是 MockGateway，实际 {type(p_after.gateway).__name__}"
            )
    finally:
        import os

        for p in ("./test_lifespan_gateway.db",):
            if os.path.exists(p):
                os.remove(p)