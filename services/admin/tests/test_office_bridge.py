"""office bridge 服务层测试 — 直接测 services/office/bridge.py（不经路由）。

覆盖：
- invoke 成功：透传 oa-agent 200 响应
- invoke tool_name 白名单：非法字符（含路径注入）→ ValueError
- oa-agent 不可达：httpx 异常 → OfficeBridgeUnavailable（路由层会翻译为 503）

不依赖真 oa-agent 进程，全程 mock httpx。
"""

from __future__ import annotations

import httpx
import pytest

from app.services.office import bridge as br


class _FakeResp:
    def __init__(self, *, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("fake error", request=None, response=self)


def _make_httpx_client(captured: dict, *, resp_status: int = 200, resp_payload: dict | None = None,
                       fail_cls: type[Exception] | None = None):
    """构造 fake AsyncClient；可选 fail_cls 让 post 抛指定异常测不可达。"""

    class _FakeCli:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def _send(self, url, **kw):
            captured["url"] = url
            if fail_cls is not None:
                raise fail_cls("simulated")
            return _FakeResp(status_code=resp_status, payload=resp_payload)

        async def post(self, url, json=None, **kw):
            captured["payload"] = json
            return await self._send(url, **kw)

        async def get(self, url, **kw):
            return await self._send(url, **kw)

    return _FakeCli


@pytest.mark.asyncio
async def test_invoke_success_forwards_payload_and_returns_json(monkeypatch):
    """invoke 正常路径：URL=OA_AGENT_URL/tools/{name}，payload={args, session_id?}。"""
    captured: dict = {}
    monkeypatch.setattr(
        br.httpx,
        "AsyncClient",
        _make_httpx_client(
            captured,
            resp_status=200,
            resp_payload={"tool": "read_docx", "ok": True, "result": {"content": "hi"}},
        ),
    )

    result = await br.invoke("read_docx", {"path": "a/b.docx"}, session_id="sess-1")

    assert result == {"tool": "read_docx", "ok": True, "result": {"content": "hi"}}
    assert captured["url"].endswith("/tools/read_docx")
    assert captured["payload"] == {"args": {"path": "a/b.docx"}, "session_id": "sess-1"}
    assert captured["timeout"] == br._TIMEOUT_INVOKE  # 60s 长超时


@pytest.mark.asyncio
async def test_invoke_404_returns_ok_false(monkeypatch):
    """oa-agent 404（工具不存在）→ invoke 规整为 ok=False（不抛异常）。"""
    captured: dict = {}
    monkeypatch.setattr(
        br.httpx, "AsyncClient", _make_httpx_client(captured, resp_status=404)
    )

    result = await br.invoke("read_docx", {})

    assert result["ok"] is False
    assert "not found" in result["error"]
    assert result["tool"] == "read_docx"


@pytest.mark.asyncio
async def test_invoke_rejects_path_injection_tool_name():
    """tool_name 含 `/` `.` `..` `%2e` 等 → ValueError（防 URL 路径注入）。"""
    for malicious in ("../health", "/admin", "a.b", "a/b", "%2e%2e", "tool name", "UPPER", ""):
        with pytest.raises(ValueError, match="非法 tool_name"):
            await br.invoke(malicious, {})


@pytest.mark.asyncio
async def test_invoke_unavailable_raises_office_bridge_unavailable(monkeypatch):
    """httpx 网络异常 → OfficeBridgeUnavailable（路由层会翻译为 HTTP 503）。"""
    monkeypatch.setattr(
        br.httpx, "AsyncClient", _make_httpx_client({}, fail_cls=httpx.ConnectError)
    )

    with pytest.raises(br.OfficeBridgeUnavailable):
        await br.invoke("read_docx", {})


@pytest.mark.asyncio
async def test_list_tools_unavailable_raises(monkeypatch):
    """list_tools 不可达同样抛 OfficeBridgeUnavailable（health 端点会降级为 ok=False）。"""
    monkeypatch.setattr(
        br.httpx, "AsyncClient", _make_httpx_client({}, fail_cls=httpx.ConnectError)
    )

    with pytest.raises(br.OfficeBridgeUnavailable):
        await br.list_tools()


@pytest.mark.asyncio
async def test_health_degrades_when_unavailable(monkeypatch):
    """oa-agent 不可达时 health 返回 ok=False（不抛，供 /office/health 端点直返）。"""
    monkeypatch.setattr(
        br.httpx, "AsyncClient", _make_httpx_client({}, fail_cls=httpx.ConnectError)
    )

    result = await br.health()

    assert result["ok"] is False
    assert result["office_tools"] == []
    assert result["total_tools"] == 0
    assert "error" in result
