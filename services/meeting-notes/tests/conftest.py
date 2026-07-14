"""pytest 全局 fixtures（会议纪要）

meeting-notes 共享 admin 的 JWT_SECRET（无 user 表，完全信任 admin token）。
所以测试时直接用 jwt 签发 token，不走 admin 服务登录。
"""
import os

# 必须在 import app 之前设环境
os.environ["DB_DRIVER"] = "sqlite"
os.environ["SQLITE_PATH"] = "./test.db"
os.environ["JWT_SECRET"] = "kk-cms-test-jwt-secret-32bytes-min-2026!"
os.environ["INIT_ADMIN_USERNAME"] = "test_admin"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest
import jwt
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """会话级 TestClient（lifespan 触发 init_db）"""
    from app.main import app

    with TestClient(app) as c:
        yield c
    # 清理测试库
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
def auth_header():
    """直接签发 JWT（meeting-notes 无 user 表，签发即用）"""
    from app.config import settings

    token = jwt.encode(
        {"sub": "test_user", "user_id": 1, "username": "tester"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}