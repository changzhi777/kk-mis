"""测试配置：用 SQLite 内存环境，避免连生产 PG"""
import os

# 必须在 import app 之前设环境
os.environ["DB_DRIVER"] = "sqlite"
os.environ["SQLITE_PATH"] = "./test.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["INIT_ADMIN_PASSWORD"] = "admin1234"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """会话级 TestClient（lifespan 触发 init_db + seed admin/admin1234）"""
    with TestClient(app) as c:
        yield c
    # 清理测试库
    for p in ("./test.db",):
        if os.path.exists(p):
            os.remove(p)


@pytest.fixture
def auth_header(client):
    """登录拿 token，返回带 Authorization 的 headers"""
    r = client.post(
        "/admin/api/v1/auth/login",
        json={"username": "admin", "password": "admin1234"},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
