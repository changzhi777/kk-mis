"""office 路由测试 — 鉴权 + 转发逻辑 + 错误码（monkeypatch bridge，不依赖真 oa-agent）。

策略：
- 鉴权测试：不绕过 get_current_user，未登录应 401
- 逻辑测试：用 dependency_overrides 绕过鉴权 + monkeypatch bridge.* 函数，
  精确验证路由转发参数、工具选择、503/501 错误码
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.main import app
from app.routes import office
from app.services.office.bridge import OfficeBridgeUnavailable

client = TestClient(app)


@pytest.fixture
def authed():
    """绕过鉴权（office 路由参数名 _user 不读属性，返回占位对象即可）。"""
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": 1})()
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ── 鉴权（未登录应 401）──────────────────────────────────────


def test_health_requires_auth():
    assert client.get("/admin/api/v1/office/health").status_code == 401


def test_call_tool_requires_auth():
    r = client.post("/admin/api/v1/office/tools", json={"tool": "read_docx", "args": {}})
    assert r.status_code == 401


def test_read_requires_auth():
    r = client.post("/admin/api/v1/office/read", json={"format": "docx", "path": "/x"})
    assert r.status_code == 401


def test_preview_requires_auth():
    assert client.get("/admin/api/v1/office/preview", params={"path": "/x"}).status_code == 401


# ── health ──────────────────────────────────────────────────


def test_health_ok(authed, monkeypatch):
    monkeypatch.setattr(
        office.bridge,
        "health",
        AsyncMock(return_value={"ok": True, "office_tools": ["read_docx"], "total_tools": 9}),
    )
    r = client.get("/admin/api/v1/office/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "read_docx" in r.json()["office_tools"]


# ── tools 列表 ──────────────────────────────────────────────


def test_tools_list_ok(authed, monkeypatch):
    monkeypatch.setattr(
        office.bridge,
        "list_tools",
        AsyncMock(return_value={"count": 9, "tools": [{"name": "read_docx"}]}),
    )
    r = client.get("/admin/api/v1/office/tools")
    assert r.status_code == 200
    assert r.json()["count"] == 9


def test_tools_list_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(
        office.bridge, "list_tools", AsyncMock(side_effect=OfficeBridgeUnavailable("conn refused"))
    )
    assert client.get("/admin/api/v1/office/tools").status_code == 503


# ── call_tool 透传 ──────────────────────────────────────────


def test_call_tool_forwards_args(authed, monkeypatch):
    mock = AsyncMock(
        return_value={"tool": "read_docx", "ok": True, "error": None, "result": {"content": "hi"}}
    )
    monkeypatch.setattr(office.bridge, "invoke", mock)
    r = client.post(
        "/admin/api/v1/office/tools",
        json={"tool": "read_docx", "args": {"path": "/x"}, "session_id": "s1"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["content"] == "hi"
    mock.assert_awaited_once_with("read_docx", {"path": "/x"}, session_id="s1")


def test_call_tool_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(office.bridge, "invoke", AsyncMock(side_effect=OfficeBridgeUnavailable("down")))
    r = client.post("/admin/api/v1/office/tools", json={"tool": "read_docx", "args": {}})
    assert r.status_code == 503


# ── read 便捷端点（format → 工具选择）──────────────────────


def test_read_picks_docx(authed, monkeypatch):
    mock = AsyncMock(return_value={"ok": True, "result": {"content": "x"}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    assert client.post("/admin/api/v1/office/read", json={"format": "docx", "path": "/a"}).status_code == 200
    mock.assert_awaited_once_with("read_docx", {"path": "/a"})


def test_read_picks_excel(authed, monkeypatch):
    mock = AsyncMock(return_value={"ok": True, "result": {}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    client.post("/admin/api/v1/office/read", json={"format": "xlsx", "path": "/a"})
    mock.assert_awaited_once_with("excel_read", {"path": "/a"})


def test_read_bad_format_400(authed):
    r = client.post("/admin/api/v1/office/read", json={"format": "pptx", "path": "/a"})
    assert r.status_code == 400


# ── preview / merge 501 占位 ────────────────────────────────


def test_preview_forwards_path(authed, monkeypatch):
    mock = AsyncMock(return_value={"tool": "docx_to_html", "ok": True, "result": {"html": "<p>hi</p>"}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    r = client.get("/admin/api/v1/office/preview", params={"path": "/a.docx"})
    assert r.status_code == 200
    assert r.json()["result"]["html"] == "<p>hi</p>"
    mock.assert_awaited_once_with("docx_to_html", {"path": "/a.docx"})


def test_preview_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(office.bridge, "invoke", AsyncMock(side_effect=OfficeBridgeUnavailable("down")))
    assert client.get("/admin/api/v1/office/preview", params={"path": "/a"}).status_code == 503


def test_merge_forwards_template(authed, monkeypatch):
    mock = AsyncMock(return_value={"tool": "merge_template", "ok": True, "result": {"output": "/o.docx"}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    r = client.post(
        "/admin/api/v1/office/merge",
        json={"template": "/t.docx", "output": "/o.docx", "context": {"name": "x"}},
    )
    assert r.status_code == 200
    mock.assert_awaited_once_with(
        "merge_template",
        {"template": "/t.docx", "output": "/o.docx", "variables": {"name": "x"}},
    )


def test_merge_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(office.bridge, "invoke", AsyncMock(side_effect=OfficeBridgeUnavailable("down")))
    r = client.post("/admin/api/v1/office/merge", json={"template": "/t", "output": "/o", "context": {}})
    assert r.status_code == 503
