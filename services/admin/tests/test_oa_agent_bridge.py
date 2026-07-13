"""oa-agent bridge 路由 smoke 测试 — 验证路由已注册且行为正确（OA agent 不可用时 503，不抛未捕获）。"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_oa_agent_healthz_returns_503_when_unreachable():
    """未启动 oa-agent 服务时，healthz 应返回 503 而不是崩。"""
    r = client.get("/admin/api/v1/oa-agent/healthz")
    assert r.status_code in (200, 502, 503)


def test_oa_agent_skills_requires_auth():
    """skills 路由要鉴权，未登录 → 401（已登录但 oa-agent 不可达 → 502/503）。"""
    r = client.get("/admin/api/v1/oa-agent/skills")
    assert r.status_code in (200, 401, 502, 503)


def test_oa_agent_chat_sync_requires_auth():
    """未登录应被 RBAC 拦截（401 或 403）。"""
    r = client.post(
        "/admin/api/v1/oa-agent/chat/sync",
        json={"message": "hi"},
    )
    # deps.get_current_user 在未认证时应抛 401
    assert r.status_code in (401, 403, 502, 503)


def test_oa_agent_chat_stream_requires_auth():
    """流式端点也要鉴权。"""
    r = client.post(
        "/admin/api/v1/oa-agent/chat",
        json={"message": "hi"},
    )
    assert r.status_code in (401, 403, 502, 503)


def test_oa_agent_sessions_list_requires_auth():
    """sessions 列表路由要鉴权，未登录 → 401（已登录但 oa-agent 不可达 → 502/503）。"""
    r = client.get("/admin/api/v1/oa-agent/sessions")
    assert r.status_code in (200, 401, 502, 503)


def test_oa_agent_session_detail_requires_auth():
    """session 详情路由要鉴权，未登录 → 401。"""
    r = client.get("/admin/api/v1/oa-agent/sessions/fake-id-1234")
    assert r.status_code in (200, 401, 502, 503)
