"""asr-cluster 鉴权测试（X-API-Key）。"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient 配 MLX_ASR_API_KEY env"""
    with patch.dict(os.environ, {"MLX_ASR_API_KEY": "test-secret-key-12345"}):
        from app.main import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_no_key():
    """MLX_ASR_API_KEY 未配置 → 503"""
    with patch.dict(os.environ, {}, clear=False):
        if "MLX_ASR_API_KEY" in os.environ:
            del os.environ["MLX_ASR_API_KEY"]
        from app.main import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def auth_header():
    return {"X-API-Key": "test-secret-key-12345"}


def test_register_requires_api_key(client):
    """无 X-API-Key → 401"""
    r = client.post(
        "/nodes/register",
        json={"id": "t1", "url": "http://x:9000", "api_key": "k"},
    )
    assert r.status_code == 401


def test_register_wrong_api_key_rejected(client):
    """错误 X-API-Key → 401"""
    r = client.post(
        "/nodes/register",
        json={"id": "t1", "url": "http://x:9000", "api_key": "k"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert r.status_code == 401


def test_register_with_correct_api_key_succeeds(client, auth_header):
    """正确 X-API-Key → 200 + 节点注册"""
    r = client.post(
        "/nodes/register",
        json={"id": "t1", "url": "http://x:9000", "api_key": "k"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_deregister_requires_api_key(client, auth_header):
    """注册成功后再注销 — 无 key 应失败"""
    client.post(
        "/nodes/register",
        json={"id": "t2", "url": "http://x:9000", "api_key": "k"},
        headers=auth_header,
    )
    r = client.delete("/nodes/t2")
    assert r.status_code == 401


def test_deregister_with_api_key_succeeds(client, auth_header):
    client.post(
        "/nodes/register",
        json={"id": "t3", "url": "http://x:9000", "api_key": "k"},
        headers=auth_header,
    )
    r = client.delete("/nodes/t3", headers=auth_header)
    assert r.status_code == 200


def test_transcribe_requires_api_key(client):
    """/transcribe 也需要鉴权（防滥用转写资源）"""
    r = client.post("/transcribe?audio_path=/tmp/test.m4a")
    assert r.status_code == 401


def test_no_env_key_returns_503(client_no_key):
    """server 端 MLX_ASR_API_KEY 未配置 → 503（fail-closed）"""
    r = client_no_key.post(
        "/nodes/register",
        json={"id": "x", "url": "http://x", "api_key": "k"},
        headers={"X-API-Key": "anything"},
    )
    assert r.status_code == 503


def test_list_nodes_no_auth_required(client):
    """GET /nodes 只读，不鉴权（运维可见性）"""
    r = client.get("/nodes")
    # 不要求 200（节点可能未启动），但不应 401
    assert r.status_code != 401


def test_root_no_auth_required(client):
    """GET / 健康检查不鉴权"""
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "asr-cluster"