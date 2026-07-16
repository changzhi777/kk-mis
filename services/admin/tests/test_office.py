"""office 路由测试 — 鉴权 + 转发逻辑 + 安全校验 + 错误码（monkeypatch bridge，不依赖真 oa-agent）。

策略：
- 鉴权测试：不绕过 get_current_user，未登录应 401
- 逻辑测试：用 dependency_overrides 绕过鉴权 + monkeypatch bridge.* 函数，
  精确验证路由转发参数、工具选择、503/501 错误码
- 安全校验：HIGH 8/9/10 修复后必须覆盖 path 遏制 + 工具白名单 + URL 注入
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.deps as deps_module
from app.deps import get_current_user
from app.main import app
from app.routes import office
from app.services.office.bridge import OfficeBridgeUnavailable

client = TestClient(app)


@pytest.fixture
def authed(monkeypatch):
    """绕过鉴权 + 权限校验。

    - dependency_overrides[get_current_user]：返回占位 user，跳过 JWT 解析；
    - monkeypatch is_super_admin → True：让 require_permission("office:tool:invoke")
      走 super_admin 直通分支（HIGH 9 后 /tools POST 改用 require_permission）。
    """
    async def _always_super(_user, _session, **_kw):
        return True

    monkeypatch.setattr(deps_module, "is_super_admin", _always_super)
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
    r = client.post("/admin/api/v1/office/read", json={"format": "docx", "path": "x"})
    assert r.status_code == 401


def test_preview_requires_auth():
    assert client.get("/admin/api/v1/office/preview", params={"path": "x"}).status_code == 401


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
        json={"tool": "read_docx", "args": {"path": "x"}, "session_id": "s1"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["content"] == "hi"
    mock.assert_awaited_once_with("read_docx", {"path": "x"}, session_id="s1")


def test_call_tool_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(office.bridge, "invoke", AsyncMock(side_effect=OfficeBridgeUnavailable("down")))
    r = client.post("/admin/api/v1/office/tools", json={"tool": "read_docx", "args": {}})
    assert r.status_code == 503


# ── read 便捷端点（format → 工具选择）──────────────────────


def test_read_picks_docx(authed, monkeypatch):
    mock = AsyncMock(return_value={"ok": True, "result": {"content": "x"}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    assert client.post("/admin/api/v1/office/read", json={"format": "docx", "path": "a"}).status_code == 200
    mock.assert_awaited_once_with("read_docx", {"path": "a"})


def test_read_picks_excel(authed, monkeypatch):
    mock = AsyncMock(return_value={"ok": True, "result": {}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    client.post("/admin/api/v1/office/read", json={"format": "xlsx", "path": "a"})
    mock.assert_awaited_once_with("excel_read", {"path": "a"})


def test_read_bad_format_400(authed):
    r = client.post("/admin/api/v1/office/read", json={"format": "pptx", "path": "a"})
    assert r.status_code == 400


# ── preview / merge 501 占位 ────────────────────────────────


def test_preview_forwards_path(authed, monkeypatch):
    mock = AsyncMock(return_value={"tool": "docx_to_html", "ok": True, "result": {"html": "<p>hi</p>"}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    r = client.get("/admin/api/v1/office/preview", params={"path": "a.docx"})
    assert r.status_code == 200
    assert r.json()["result"]["html"] == "<p>hi</p>"
    mock.assert_awaited_once_with("docx_to_html", {"path": "a.docx"})


def test_preview_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(office.bridge, "invoke", AsyncMock(side_effect=OfficeBridgeUnavailable("down")))
    assert client.get("/admin/api/v1/office/preview", params={"path": "a"}).status_code == 503


def test_merge_forwards_template(authed, monkeypatch):
    mock = AsyncMock(return_value={"tool": "merge_template", "ok": True, "result": {"output": "o.docx"}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    r = client.post(
        "/admin/api/v1/office/merge",
        json={"template": "t.docx", "output": "o.docx", "context": {"name": "x"}},
    )
    assert r.status_code == 200
    mock.assert_awaited_once_with(
        "merge_template",
        {"template": "t.docx", "output": "o.docx", "variables": {"name": "x"}},
    )


def test_merge_unreachable_503(authed, monkeypatch):
    monkeypatch.setattr(office.bridge, "invoke", AsyncMock(side_effect=OfficeBridgeUnavailable("down")))
    r = client.post("/admin/api/v1/office/merge", json={"template": "t", "output": "o", "context": {}})
    assert r.status_code == 503


# ── HIGH 8：路径遏制（绝对路径 / .. 遍历）───────────────────


def test_read_rejects_absolute_path(authed, monkeypatch):
    """绝对路径透传可能让任意登录用户读 /etc/passwd。"""
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post("/admin/api/v1/office/read", json={"format": "docx", "path": "/etc/passwd"})
    assert r.status_code == 400
    assert "绝对路径" in r.json()["detail"]
    invoke_mock.assert_not_awaited()


def test_read_rejects_dotdot(authed, monkeypatch):
    """相对 `..` 遍历也应拦截。"""
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/read",
        json={"format": "docx", "path": "docs/../../secret"},
    )
    assert r.status_code == 400
    assert ".." in r.json()["detail"]
    invoke_mock.assert_not_awaited()


def test_read_rejects_windows_absolute(authed, monkeypatch):
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/read",
        json={"format": "docx", "path": "C:\\Windows\\win.ini"},
    )
    assert r.status_code == 400
    invoke_mock.assert_not_awaited()


def test_read_rejects_unc_path(authed, monkeypatch):
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/read",
        json={"format": "docx", "path": "\\\\attacker\\share"},
    )
    assert r.status_code == 400
    invoke_mock.assert_not_awaited()


def test_preview_rejects_absolute_path(authed, monkeypatch):
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.get("/admin/api/v1/office/preview", params={"path": "/etc/shadow"})
    assert r.status_code == 400
    invoke_mock.assert_not_awaited()


def test_merge_rejects_absolute_template(authed, monkeypatch):
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/merge",
        json={"template": "/etc/passwd", "output": "o.docx", "context": {}},
    )
    assert r.status_code == 400
    assert "template" in r.json()["detail"]
    invoke_mock.assert_not_awaited()


def test_merge_rejects_absolute_output(authed, monkeypatch):
    """output 是写文件，绝对路径可覆盖任意 docx，必须拦。"""
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/merge",
        json={"template": "t.docx", "output": "/opt/app/oa-agent/config.yaml", "context": {}},
    )
    assert r.status_code == 400
    assert "output" in r.json()["detail"]
    invoke_mock.assert_not_awaited()


def test_read_accepts_nested_relative_path(authed, monkeypatch):
    """合法相对路径（含子目录）应放行。"""
    mock = AsyncMock(return_value={"ok": True, "result": {}})
    monkeypatch.setattr(office.bridge, "invoke", mock)
    r = client.post(
        "/admin/api/v1/office/read",
        json={"format": "docx", "path": "contracts/2026/lease.docx"},
    )
    assert r.status_code == 200
    mock.assert_awaited_once_with("read_docx", {"path": "contracts/2026/lease.docx"})


# ── HIGH 9：/tools 工具白名单 + require_permission ───────────


def test_call_tool_rejects_non_office_tool(authed, monkeypatch):
    """req.tool 不在 OFFICE_TOOLS 白名单 → 400（防越权调 query_weather 等）。"""
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/tools",
        json={"tool": "query_weather", "args": {"city": "x"}},
    )
    assert r.status_code == 400
    assert "白名单" in r.json()["detail"]
    invoke_mock.assert_not_awaited()


def test_call_tool_rejects_path_traversal_tool_name(authed, monkeypatch):
    """`../health` 这种路径注入 tool_name → 400（白名单先拦，bridge.invoke 再兜底）。"""
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post(
        "/admin/api/v1/office/tools",
        json={"tool": "../health", "args": {}},
    )
    assert r.status_code == 400
    invoke_mock.assert_not_awaited()


def test_call_tool_rejects_empty_tool(authed, monkeypatch):
    invoke_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(office.bridge, "invoke", invoke_mock)
    r = client.post("/admin/api/v1/office/tools", json={"tool": "", "args": {}})
    assert r.status_code == 400
    invoke_mock.assert_not_awaited()


def test_call_tool_permission_denied_without_override():
    """没有 override is_super_admin 时，占位 user 应被 require_permission 拒为 403。

    覆盖 HIGH 9：未授权用户（无 office:tool:invoke 权限 + 非 super_admin）
    调 /tools POST 必须返回 403，而不是 200（原 bug 仅 get_current_user）。
    """
    # 仅 override get_current_user（让认证通过），但不 override is_super_admin
    # → DB 无 user_id=999999 → is_super_admin=False + perms=[] → require_permission 403
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": 999999})()
    try:
        r = client.post(
            "/admin/api/v1/office/tools",
            json={"tool": "read_docx", "args": {}},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── HIGH 10：bridge.invoke tool_name 正则白名单 ─────────────


@pytest.mark.asyncio
async def test_bridge_invoke_rejects_path_injection():
    """bridge.invoke 自身的纵深防御：tool_name 含 `/` `.` 等非法字符 → ValueError。"""
    from app.services.office import bridge as br

    for malicious in ("../health", "/admin", "a.b", "a/b", "%2e%2e", "tool name", "UPPER"):
        with pytest.raises(ValueError, match="非法 tool_name"):
            await br.invoke(malicious, {})


@pytest.mark.asyncio
async def test_bridge_invoke_accepts_valid_name(monkeypatch):
    """合法工具名能正常进入 httpx 调用（mock 掉网络层）。"""
    from app.services.office import bridge as br

    captured: dict = {}

    class _FakeResp:
        status_code = 404  # 让 invoke 走"工具不存在"分支，不发真请求

        def json(self):
            return {}

        def raise_for_status(self):
            pass

    class _FakeCli:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kw):
            captured["url"] = url
            return _FakeResp()

    monkeypatch.setattr(br.httpx, "AsyncClient", _FakeCli)
    result = await br.invoke("read_docx", {"path": "a"})
    assert result["ok"] is False  # 404 分支
    assert captured["url"].endswith("/tools/read_docx")
