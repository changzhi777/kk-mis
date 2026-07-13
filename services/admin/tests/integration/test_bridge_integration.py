"""跨服务集成测试：admin → oa-agent bridge

覆盖：
- 健康检查透传
- 同步对话转发
- 不可达降级
- 鉴权
"""

import pytest


def test_oa_agent_healthz_passthrough(client, oa_agent_server, auth_header):
    """bridge /healthz 透传 oa-agent 响应"""
    r = client.get("/admin/api/v1/oa-agent/healthz", headers=auth_header)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_oa_agent_skills_list_passthrough(client, oa_agent_server, auth_header):
    """bridge /skills 透传"""
    r = client.get("/admin/api/v1/oa-agent/skills", headers=auth_header)
    assert r.status_code == 200
    body = r.json()
    assert "skills" in body
    assert isinstance(body["skills"], list)
    # 应有至少 1 个 skill（oa-agent seed）
    # 不强求具体 skill（oa-agent 内部决定）


def test_oa_agent_chat_sync_simple_message(client, oa_agent_server, auth_header):
    """同步对话：简单问题（不调工具）应能快速返回"""
    r = client.post(
        "/admin/api/v1/oa-agent/chat/sync",
        json={"message": "1+1=?"},
        headers=auth_header,
        timeout=60,  # ReAct 可能慢
    )
    # oa-agent 在测试环境可能没真 LLM key → 可能 5xx
    # 但 bridge 必须能转发（4xx/5xx 都算"转发成功"，不算 bridge bug）
    assert r.status_code in (200, 500, 502, 503, 504)
    if r.status_code == 200:
        body = r.json()
        assert "session_id" in body
        assert "final" in body
    else:
        # LLM 不可用是预期的（测试环境无 key）
        body = r.json()
        assert "detail" in body  # bridge 错误格式


def test_oa_agent_chat_sync_requires_auth(client, oa_agent_server):
    """未登录 → 401"""
    r = client.post(
        "/admin/api/v1/oa-agent/chat/sync",
        json={"message": "test"},
    )
    assert r.status_code == 401


def test_oa_agent_skills_requires_auth(client, oa_agent_server):
    """未登录 → 401"""
    r = client.get("/admin/api/v1/oa-agent/skills")
    assert r.status_code == 401


def test_oa_agent_healthz_no_auth_required(client, oa_agent_server):
    """/healthz 公开（无需登录，运维探活用）"""
    r = client.get("/admin/api/v1/oa-agent/healthz")
    assert r.status_code == 200


# ── 不可达降级（停 oa-agent 模拟） ────────────────────────────────


def test_bridge_returns_503_when_oa_agent_down():
    """oa-agent 不可达时 bridge 返回 503 + 错误信息

    用独立 TestClient（不共享 session fixture 的 client，避免污染）。
    通过 patch out bridge 的 OA_AGENT_URL 指向无效端口。
    """
    import os

    os.environ["DB_DRIVER"] = "sqlite"
    os.environ["SQLITE_PATH"] = "./test_bridge_down.db"
    os.environ["JWT_SECRET"] = "test-secret-key-1234567890123456"
    os.environ["INIT_ADMIN_PASSWORD"] = "admin1234"

    # 用独立子进程跑 admin（避免 oa-agent 端 fixture 影响）
    # 改 oa_agent_bridge.OA_AGENT_URL 指向无效端口
    from app.routes import oa_agent_bridge
    from fastapi.testclient import TestClient

    original_url = oa_agent_bridge.OA_AGENT_URL
    oa_agent_bridge.OA_AGENT_URL = "http://127.0.0.1:1"  # 不会有人监听

    from app.main import app

    with TestClient(app) as c:
        # 登录拿 token
        r = c.post(
            "/admin/api/v1/auth/login",
            json={"username": "admin", "password": "admin1234"},
        )
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # 调 healthz → 503
        r2 = c.get("/admin/api/v1/oa-agent/healthz", headers=h)
        assert r2.status_code == 503
        assert "不可达" in r2.json()["detail"]

        # 调 chat/sync → 502
        r3 = c.post(
            "/admin/api/v1/oa-agent/chat/sync",
            json={"message": "hi"},
            headers=h,
        )
        # bridge 的 chat_sync 在 except 时也 raise HTTPException(502)
        assert r3.status_code in (502, 503)

    # 还原
    oa_agent_bridge.OA_AGENT_URL = original_url

    # 清理
    if os.path.exists("./test_bridge_down.db"):
        os.remove("./test_bridge_down.db")