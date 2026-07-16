"""动态二维码防伪测试（services/dynamic_code.py · V1）

覆盖：
- generate 产码格式（payload_b64.sig）+ expire_at/ttl 正确
- verify 成功返回 card_id/nonce（正常往返）
- 验签失败（篡改签名）/ 格式错误 / 过期码 被拒

注：Redis 在测试环境不可用（cache fail-open，get_json 恒返回 None），
故防重放 nonce 二次使用不会被拦截——本测试不覆盖重放路径，仅覆盖签名+时效+格式。
"""
import time

import pytest

from app.services import dynamic_code


def test_generate_format_and_verify_roundtrip():
    """generate 产出 {code, expire_at, ttl}，code 格式 payload_b64.sig；verify 成功返回 card_id。"""
    result = dynamic_code.generate(card_id=42, ttl=30)
    assert "code" in result
    assert "expire_at" in result
    assert "ttl" in result
    assert result["ttl"] == 30

    code = result["code"]
    # 格式：base64url(base64url_payload).hex_sig
    assert "." in code
    parts = code.split(".")
    assert len(parts) == 2
    assert len(parts[1]) == 64  # HMAC-SHA256 hex = 64 chars

    # expire_at 应在 [now, now+30] 之间
    now = int(time.time())
    assert now <= result["expire_at"] <= now + 31

    # verify 异步，用 asyncio.run 跑（不依赖 pytest-asyncio mode）
    import asyncio

    verified = asyncio.run(dynamic_code.verify(code))
    assert verified["card_id"] == 42
    assert "nonce" in verified
    assert len(verified["nonce"]) > 0


@pytest.mark.asyncio
async def test_verify_rejects_tampered_signature():
    """篡改签名 → ValueError（验签恒定时间比较失败）。"""
    result = dynamic_code.generate(card_id=7)
    code = result["code"]
    payload_b64, sig = code.rsplit(".", 1)
    # 翻转最后一个 hex 字符
    last_char = sig[-1]
    flipped = "0" if last_char != "0" else "1"
    tampered = f"{payload_b64}.{sig[:-1]}{flipped}"

    with pytest.raises(ValueError, match="签名无效"):
        await dynamic_code.verify(tampered)


@pytest.mark.asyncio
async def test_verify_rejects_malformed_and_expired():
    """格式错误 → ValueError；过期码 → ValueError。"""
    # 空 / 无点分隔
    with pytest.raises(ValueError, match="格式错误"):
        await dynamic_code.verify("")
    with pytest.raises(ValueError, match="格式错误"):
        await dynamic_code.verify("nodelimiter")

    # 过期码：ttl=0 使 expire_at ≈ now，verify 时 now > exp 必然成立
    expired = dynamic_code.generate(card_id=1, ttl=0)
    # 等 1 秒确保过期
    import asyncio as _aio
    await _aio.sleep(1.0)
    with pytest.raises(ValueError, match="已过期"):
        await dynamic_code.verify(expired["code"])
