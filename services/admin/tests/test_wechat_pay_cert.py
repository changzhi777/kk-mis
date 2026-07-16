"""WechatPayV3Gateway X.509 平台证书 + Wechatpay-Serial 校验单测（P0 Day 2 缺口 #2）

覆盖：
1. test_load_pem_x509_cert —— X.509 PEM 文件可正确加载
2. test_load_invalid_cert_raises —— 无效证书 raise RuntimeError
3. test_extract_public_key —— 从证书提取公钥并可用于 verify
4. test_single_cert_path —— 单个 platform_cert_path 构造
5. test_multi_certs_dict —— 多证书 platform_certs dict 构造
6. test_cert_dir_scan —— platform_cert_dir 目录扫描
7. test_get_cert_by_serial_hit —— 已知 serial 返回对应证书
8. test_get_cert_by_serial_miss_raises —— 未知 serial raise ValueError
9. test_verify_callback_correct_serial —— 正确 serial 验签通过
10. test_verify_callback_wrong_serial_rejected —— 错误 serial 验签拒绝

证书自签：用 cryptography 生成自签 RSA + X.509，序列号固定可测可控。
"""
from __future__ import annotations

import base64
import datetime
import json

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID

from app.services.wechat_pay import (
    WechatNotify,
    WechatPayV3Gateway,
    _extract_public_key,
    _load_platform_cert,
    _normalize_serial,
)

_API_V3_KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes


# ── Fixtures：自签 X.509 + RSA 私钥 ──────────────────────

def _gen_self_signed_cert(
    common_name: str = "Test",
    serial: int | None = None,
    valid_days: int = 30,
    key_size: int = 2048,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """生成 (x509.Certificate, RSA private key) 自签对。

    Cert V3 必须有 serial_number——不传则用 `x509.random_serial_number()`。
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    serial_number = serial if serial is not None else x509.random_serial_number()
    # 用 UTC-aware 避免 Python 3.13 datetime.utcnow() 弃用警告
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(serial_number)
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=valid_days))
        .sign(private_key, hashes.SHA256())
    )
    return cert, private_key


def _write_cert_pem(path: str, cert: x509.Certificate) -> None:
    pem = cert.public_bytes(serialization.Encoding.PEM)
    with open(path, "wb") as f:
        f.write(pem)


def _serialize_cert(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


@pytest.fixture
def tmp_cert_dir(tmp_path):
    """空子目录 fixture：供 platform_cert_dir 扫描测试用。"""
    return tmp_path


@pytest.fixture
def single_cert_path(tmp_path) -> tuple[str, x509.Certificate, rsa.RSAPrivateKey]:
    """单证书文件 fixture：path + cert + 关联私钥。"""
    cert, priv = _gen_self_signed_cert(common_name="wc-1", serial=0x1234567890ABCDEF)
    p = tmp_path / "platform.pem"
    _write_cert_pem(str(p), cert)
    return str(p), cert, priv


@pytest.fixture
def two_certs(tmp_path) -> tuple[dict[str, str], dict[str, rsa.RSAPrivateKey]]:
    """双证书 dict fixture：(serial→path 字典) + (serial→私钥 字典)。"""
    cert_a, priv_a = _gen_self_signed_cert(common_name="wc-A", serial=0xAAAAAAA1)
    cert_b, priv_b = _gen_self_signed_cert(common_name="wc-B", serial=0xBBBBBBB2)
    path_a = tmp_path / "cert_a.pem"
    path_b = tmp_path / "cert_b.pem"
    _write_cert_pem(str(path_a), cert_a)
    _write_cert_pem(str(path_b), cert_b)

    def _norm(c):
        s = _normalize_serial(c)
        return s.upper() if isinstance(s, str) else s

    sa = _norm(cert_a).upper() if isinstance(_norm(cert_a), str) else format(_norm(cert_a), "X")
    sb = _norm(cert_b).upper() if isinstance(_norm(cert_b), str) else format(_norm(cert_b), "X")

    return (
        {sa: str(path_a), sb: str(path_b)},
        {sa: priv_a, sb: priv_b},
    )


# ── 1. X.509 PEM 加载 ─────────────────────────────────────

def test_load_pem_x509_cert(single_cert_path):
    """X.509 PEM 文件可正确加载。"""
    path, cert, _ = single_cert_path
    loaded = _load_platform_cert(path)
    assert isinstance(loaded, x509.Certificate)
    # 序列号应能取到（int 或 bytes 都行）
    sn = loaded.serial_number
    assert isinstance(sn, (int, bytes))
    # 公钥应能取出
    pk = _extract_public_key(loaded)
    from cryptography.hazmat.primitives.asymmetric import rsa
    assert isinstance(pk, rsa.RSAPublicKey)


# ── 2. 无效证书 raise RuntimeError ──────────────────────

def test_load_invalid_cert_raises(tmp_path):
    """无效证书（文件不存在 / 非 PEM / 非证书）应 raise RuntimeError。"""
    # (a) 文件不存在
    with pytest.raises(RuntimeError):
        _load_platform_cert(str(tmp_path / "nonexistent.pem"))
    # (b) 不是 PEM
    junk = tmp_path / "junk.pem"
    junk.write_bytes(b"this is not a PEM cert at all")
    with pytest.raises(RuntimeError):
        _load_platform_cert(str(junk))
    # (c) 是 PEM 但不是 cert（裸公钥）
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_key = tmp_path / "pubkey.pem"
    pub_key.write_bytes(pub_pem)
    with pytest.raises(RuntimeError):
        _load_platform_cert(str(pub_key))


# ── 3. 公钥提取并可用于签名 verify ─────────────────────

def test_extract_public_key(single_cert_path):
    """extract_public_key 提出的公钥可用于 verify 用对应私钥签的签名。"""
    _, cert, priv = single_cert_path
    pub = _extract_public_key(cert)
    msg = b"hello world"
    sig = priv.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    pub.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())  # 不抛即通过


# ── 4. 单证书 platform_cert_path 构造 ─────────────────

def test_single_cert_path(single_cert_path):
    """单证书 path 构造：自动归一化 serial 加入 _cert_map。"""
    path, cert, _ = single_cert_path
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_cert_path=path,
    )
    # cert map 应有 1 项
    serials = gw.list_cert_serials()
    assert len(serials) == 1
    assert gw.has_cert_for_serial(serials[0]) is True
    assert gw.has_cert_for_serial("UNKNOWN_SERIAL") is False
    # legacy key 应为 None
    # (隐式：单证书模式没有 legacy)


# ── 5. 多证书 platform_certs dict 构造 ────────────────

def test_multi_certs_dict(two_certs):
    """多证书 dict 构造：每个 serial 对应独立证书。"""
    plat_certs, _ = two_certs
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_certs=plat_certs,
    )
    serials = set(gw.list_cert_serials())
    expected = set(plat_certs.keys())
    assert serials == expected
    for s in expected:
        assert gw.has_cert_for_serial(s) is True


# ── 6. 目录扫描 ─────────────────────────────────────

def test_cert_dir_scan(two_certs, tmp_path):
    """platform_cert_dir 扫描目录下所有 .pem / .crt。"""
    plat_certs, _ = two_certs
    cert_dir = tmp_path / "scan_dir"
    cert_dir.mkdir()
    # 把两张证书都拷贝到新目录里
    import shutil
    for src in plat_certs.values():
        shutil.copy(src, cert_dir / src.split("/")[-1])
    # 改名其中一个为 .crt 验证扩展名识别
    pem_files = list(cert_dir.glob("*.pem"))
    assert len(pem_files) >= 2
    renamed = pem_files[0].with_suffix(".crt")
    pem_files[0].rename(renamed)
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_cert_dir=str(cert_dir),
    )
    serials = gw.list_cert_serials()
    assert len(serials) >= 2
    # 都应该能被 find
    for s in serials:
        assert gw.has_cert_for_serial(s) is True


# ── 7. get_cert_by_serial 命中 ────────────────────────

def test_get_cert_by_serial_hit(two_certs):
    """已知 serial 返回对应 X.509 证书。"""
    plat_certs, privs = two_certs
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_certs=plat_certs,
    )
    # 取一个 serial
    serial_a = next(iter(plat_certs.keys()))
    cert = gw._cert_by_serial(serial_a)
    assert isinstance(cert, x509.Certificate)


# ── 8. get_cert_by_serial 未命中 raise ValueError ─────

def test_get_cert_by_serial_miss_raises(two_certs):
    """未知 serial raise ValueError（应用层据此决定→401 还是等证书刷新）。"""
    plat_certs, _ = two_certs
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_certs=plat_certs,
    )
    with pytest.raises(ValueError):
        gw._cert_by_serial("DEADBEEF_NOT_IN_MAP")


# ── 9. verify_callback 正确 serial 验签通过 ─────────────

def test_verify_callback_correct_serial(two_certs):
    """headers.Wechatpay-Serial 命中真实证书 → verify_callback 返回 True。"""
    plat_certs, privs = two_certs
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_certs=plat_certs,
    )
    # 选第 2 张证书模拟微信（"当前回调"用新证）
    serial_b = list(plat_certs.keys())[1]
    priv_b = privs[serial_b]
    body = b'{"id":"evt_real_serial","resource":{"nonce":"n","ciphertext":"c","associated_data":""}}'
    ts = "1700000000"  # 极早时间戳避免时间窗失败（check_timestamp 默认 ±300s，可能失败——见说明）
    nonce = "nonce_correct"
    msg = f"{ts}\n{nonce}\n".encode() + body + b"\n"
    sig = base64.b64encode(
        priv_b.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    headers = {
        "Wechatpay-Serial": serial_b,
        "Wechatpay-Timestamp": ts,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": sig,
    }
    # 时间戳 1700000000 = 2023-11-14 远超 tolerance=300s，需要 patch
    import time as _time
    now = 1700000000
    # 直接构造 gw with 长 tolerance
    gw_long = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_certs=plat_certs,
        tolerance_seconds=10**9,  # 足够大以跳过时间窗
    )
    assert gw_long.verify_callback(headers, body) is True


# ── 10. verify_callback 错误 serial 验签拒绝 ───────────

def test_verify_callback_wrong_serial_rejected(two_certs):
    """headers.Wechatpay-Serial 命中错证书 → verify_callback 返回 False。"""
    plat_certs, privs = two_certs
    gw = WechatPayV3Gateway(
        api_v3_key=_API_V3_KEY,
        platform_certs=plat_certs,
        tolerance_seconds=10**9,  # 跳过时间窗
    )
    # 用证书 B 的私钥签消息，但 headers 报证书 A 的 serial
    serial_a = list(plat_certs.keys())[0]
    serial_b = list(plat_certs.keys())[1]
    priv_b = privs[serial_b]
    body = b'{"id":"evt_attack"}'
    ts = "1700000000"
    nonce = "nonce_attack"
    msg = f"{ts}\n{nonce}\n".encode() + body + b"\n"
    sig = base64.b64encode(
        priv_b.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    headers = {
        "Wechatpay-Serial": serial_a,  # 错证书
        "Wechatpay-Timestamp": ts,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": sig,
    }
    # 攻击者期望网关用 cert_a 验，但签名是用 cert_b 私钥签的 → 验签 False
    assert gw.verify_callback(headers, body) is False
    # 反之：签名用的 cert_b，headers 报 cert_b 也走不通（因为之前 send_with cert_a）
    # 这里要测的是"轮换期"攻击：serial 错即拒
    # 同样测：完全未知的 serial
    headers["Wechatpay-Serial"] = "00DEADBEEF"
    assert gw.verify_callback(headers, body) is False
