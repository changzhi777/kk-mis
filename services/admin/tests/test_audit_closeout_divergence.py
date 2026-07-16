"""36 项审计收尾：验证代码与记忆中四处偏差已对齐。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock


def test_login_rate_limit_enforced(client, monkeypatch):
    """同一 IP 连续失败 10 次后，第 11 次登录应被限流。"""
    from app import cache

    calls: list[tuple[str, int, int]] = []

    async def fake_rate_limit_check(key: str, max_count: int, window_seconds: int) -> bool:
        calls.append((key, max_count, window_seconds))
        return len(calls) <= max_count

    monkeypatch.setattr(cache, "rate_limit_check", fake_rate_limit_check)

    responses = [
        client.post(
            "/admin/api/v1/auth/login",
            json={"username": "unknown-audit-user", "password": "wrong"},
        )
        for _ in range(11)
    ]

    assert [r.status_code for r in responses[:10]] == [401] * 10
    assert responses[10].status_code == 429
    assert len(calls) == 11
    assert all(key.startswith("ratelimit:login:") for key, _, _ in calls)
    assert all(limit == 10 and window == 60 for _, limit, window in calls)


def test_register_rate_limit_comment_corrected():
    """注册限流注释应与实际 1000/小时/IP 阈值一致。"""
    source = Path(__file__).parents[1].joinpath("app/routes/auth.py").read_text()
    assert "1000 次/小时/IP" in source
    assert "5 次/小时/IP" not in source


def test_auth_header_session_cached(client, auth_header, request):
    """auth_header 通过 session fixture 复用同一个 token。"""
    token_1 = auth_header["Authorization"]
    token_2 = request.getfixturevalue("auth_header")["Authorization"]

    assert token_1 == token_2
    cached_fixture = request._fixture_defs["_cached_token"]
    assert cached_fixture.scope == "session"
    assert cached_fixture.cached_result is not None


def test_notifier_close_client_in_lifespan(monkeypatch):
    """应用 lifespan 退出时应 await notifier.close_client。"""
    from app import main as main_module
    from app import cache
    from app.services import notifier, payment, payment_fulfillment

    close_notifier = AsyncMock()

    async def fake_init_db():
        return None

    async def fake_close_db():
        return None

    async def fake_poller():
        await asyncio.Event().wait()

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "close_db", fake_close_db)
    monkeypatch.setattr(cache, "init", AsyncMock())
    monkeypatch.setattr(cache, "close", AsyncMock())
    monkeypatch.setattr(payment, "build_gateway_from_settings", lambda settings: object())
    monkeypatch.setattr(payment, "set_gateway", Mock())
    monkeypatch.setattr(payment_fulfillment, "start_retry_poller", fake_poller)
    monkeypatch.setattr(notifier, "close_client", close_notifier)

    async def run_lifespan():
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(run_lifespan())
    close_notifier.assert_awaited_once_with()
