"""动态二维码防伪（V1，2026-07-13 深度升级）。

码格式：base64url(payload_json) + "." + hmac_hex
payload = {card_id, nonce, exp（unix 秒）}
签名：HMAC-SHA256(payload_b64, jwt_secret) —— 复用 jwt_secret，不可伪造
有效期：30s（持卡人侧每 30s 刷新）
防重放：nonce 验证成功后存 Redis（TTL 120s），同码二次使用即拒

持卡人侧 generate（30s 刷新展示），商家扫码 verify 后核销。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from ..config import settings

_TTL = 30  # 动态码有效期（秒）
_REPLAY_TTL = 120  # nonce 防重放窗口（>TTL 容余）


def _sign(payload_b64: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()


def _b64encode(obj: Any) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def _b64decode(s: str) -> Any:
    return json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)))


def generate(card_id: int, ttl: int = _TTL) -> dict:
    """持卡人侧生成动态码。返回 {code, expire_at, ttl}。"""
    nonce = secrets.token_urlsafe(16)
    exp = int(time.time()) + ttl
    payload_b64 = _b64encode({"card_id": card_id, "nonce": nonce, "exp": exp})
    sig = _sign(payload_b64)
    return {"code": f"{payload_b64}.{sig}", "expire_at": exp, "ttl": ttl}


async def verify(code: str) -> dict:
    """商家核销侧验证动态码。成功返回 {card_id, nonce}，失败抛 ValueError。"""
    from .. import cache  # 延迟 import 避免循环

    if not code or "." not in code:
        raise ValueError("动态码格式错误")
    payload_b64, sig = code.rsplit(".", 1)
    # 1. 验签（恒定时间比较防时序攻击）
    if not hmac.compare_digest(sig, _sign(payload_b64)):
        raise ValueError("动态码签名无效")
    # 2. 解 payload
    try:
        payload = _b64decode(payload_b64)
    except Exception:
        raise ValueError("动态码 payload 无效")
    # 3. 验时效
    if int(time.time()) > int(payload.get("exp", 0)):
        raise ValueError("动态码已过期")
    # 4. 防重放：nonce 首次用 get_json miss→set 成功；hit=重放
    nonce_key = f"dyncode:nonce:{payload['nonce']}"
    if await cache.get_json(nonce_key) is not None:
        raise ValueError("动态码已使用（防重放）")
    await cache.set_json(nonce_key, {"card_id": payload["card_id"]}, ttl=_REPLAY_TTL)
    return {"card_id": payload["card_id"], "nonce": payload["nonce"]}
