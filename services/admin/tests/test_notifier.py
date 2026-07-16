"""notifier 服务测试 — 适配 2026-07-16 重写接口（_webhook_url 函数 + _get_client 复用 + raise_for_status）。

覆盖：
- 配了 webhook URL → 发 POST {event, data}
- URL 为空 → 直接 return，_get_client 不被调用
- post 抛异常或 5xx → 静默吞错（通知是旁路，不阻塞业务）
"""
from __future__ import annotations

import pytest

import app.services.notifier as notifier_mod


class _FakeResp:
    """模拟 httpx.Response（notify 调 raise_for_status，200 不抛）。"""

    status_code = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeCli:
    """假 client：记录 post 的 url/json。"""

    def __init__(self, *a, **kw):
        self.captured: dict = {}

    async def post(self, url, json=None, **kw):
        self.captured = {"url": url, "json": json}
        return _FakeResp()


class _FailCli:
    """post 抛异常的 client。"""

    async def post(self, url, json=None, **kw):
        raise RuntimeError("simulated network failure")


@pytest.mark.asyncio
async def test_notify_posts_event_and_payload(monkeypatch):
    """配了 URL → 发 POST {event, data}，URL + payload 正确。"""
    monkeypatch.setattr(notifier_mod, "_webhook_url", lambda: "http://example.test/hook")
    cli = _FakeCli()
    monkeypatch.setattr(notifier_mod, "_get_client", lambda: _async_return(cli))
    await notifier_mod.notify("新订单", {"id": 42, "amount": 99.5})
    assert cli.captured["url"] == "http://example.test/hook"
    assert cli.captured["json"] == {"event": "新订单", "data": {"id": 42, "amount": 99.5}}


async def _async_return(val):
    """helper：把 _get_client 包成返回既定 client 的 coroutine 函数。"""
    return val


@pytest.mark.asyncio
async def test_notify_skips_when_no_url(monkeypatch):
    """URL 为空 → 直接 return，_get_client 不应被调用。"""
    called: list = []
    monkeypatch.setattr(notifier_mod, "_webhook_url", lambda: "")
    monkeypatch.setattr(
        notifier_mod,
        "_get_client",
        lambda: called.append("init") or _async_return(_FakeCli()),
    )
    await notifier_mod.notify("任意事件", {"x": 1})
    assert called == []  # _get_client 未触发


@pytest.mark.asyncio
async def test_notify_silently_swallows_http_errors(monkeypatch):
    """post 抛异常 → 静默吞错（不向上抛，通知是旁路）。"""
    monkeypatch.setattr(notifier_mod, "_webhook_url", lambda: "http://example.test/hook")
    monkeypatch.setattr(notifier_mod, "_get_client", lambda: _async_return(_FailCli()))
    # 不应抛异常（notifier 契约：失败静默）
    await notifier_mod.notify("失败的订单", {"id": 1})


@pytest.mark.asyncio
async def test_notify_swallows_5xx_via_raise_for_status(monkeypatch):
    """5xx → raise_for_status 抛 → 静默吞错（MEDIUM：原静默 except: pass，现结构化日志）。"""
    monkeypatch.setattr(notifier_mod, "_webhook_url", lambda: "http://example.test/hook")

    class _ServerErrorCli:
        async def post(self, url, json=None, **kw):
            r = _FakeResp()
            r.status_code = 500
            return r

    monkeypatch.setattr(notifier_mod, "_get_client", lambda: _async_return(_ServerErrorCli()))
    await notifier_mod.notify("server_err", {"id": 1})  # 不抛即通过
