"""测试配置：用 SQLite 内存环境，避免连生产 PG"""
import os

# 必须在 import app 之前设环境
os.environ["DB_DRIVER"] = "sqlite"
os.environ["SQLITE_PATH"] = "./test.db"
os.environ["JWT_SECRET"] = "test-secret-key-1234567890123456"
os.environ["INIT_ADMIN_PASSWORD"] = "admin1234"
os.environ["LOG_LEVEL"] = "WARNING"

import signal
import socket
import subprocess
import sys
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

# 跨服务集成：oa-agent 启动端口（与 bridge 默认 :9001 保持一致便于注入 env）
OA_AGENT_TEST_PORT = 19001
OA_AGENT_BASE_URL = f"http://127.0.0.1:{OA_AGENT_TEST_PORT}"

# 必须在 import app 之前设 env（让 bridge 读到测试 URL）
os.environ["OA_AGENT_URL"] = OA_AGENT_BASE_URL

# bridge 是模块级常量 import 时锁定。conftest import 在 app 之后，
# 但 TestClient lifespan 内 import app 之前 bridge 已 import 完（os.environ 已被读）。
# 这里在 conftest 末尾强制 patch bridge 模块级常量（确保指向测试端口）。
from app.routes import oa_agent_bridge as _bridge_module  # noqa: E402

_bridge_module.OA_AGENT_URL = OA_AGENT_BASE_URL


def _port_in_use(port: int) -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_port_open(port: int, timeout: float = 30.0) -> bool:
    """等待端口就绪"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port):
            return True
        time.sleep(0.2)
    return False


@pytest.fixture(scope="session")
def oa_agent_server():
    """session-scoped：启动 oa-agent 子进程（:19001）"""
    if _port_in_use(OA_AGENT_TEST_PORT):
        # 已有人跑 oa-agent（开发/生产），跳过启动但仍可测
        yield OA_AGENT_BASE_URL
        return

    oa_agent_dir = os.path.expanduser("~/Documents/Claude/Projects/oa-agent")
    if not os.path.exists(oa_agent_dir):
        pytest.skip(f"oa-agent 项目目录不存在: {oa_agent_dir}")

    env = {
        **os.environ,
        "OA_AGENT_HOST": "127.0.0.1",
        "OA_AGENT_PORT": str(OA_AGENT_TEST_PORT),
        "PYTHONPATH": os.path.join(oa_agent_dir, "src"),
    }
    log_path = f"/tmp/oa_agent_test_{OA_AGENT_TEST_PORT}.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "oa_agent.api:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(OA_AGENT_TEST_PORT),
            "--log-level",
            "info",
        ],
        cwd=oa_agent_dir,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    try:
        if not _wait_port_open(OA_AGENT_TEST_PORT, timeout=30):
            log_file.close()
            log_content = open(log_path).read()
            proc.terminate()
            pytest.skip(
                f"oa-agent 启动失败（端口 {OA_AGENT_TEST_PORT} 未就绪），跳过 bridge 集成测试；"
                f"日志见 {log_path}"
            )
        # 等 healthz 端点响应
        healthz_ok = False
        for _ in range(40):
            try:
                r = httpx.get(f"{OA_AGENT_BASE_URL}/healthz", timeout=2.0)
                if r.status_code == 200:
                    healthz_ok = True
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not healthz_ok:
            log_file.close()
            log_content = open(log_path).read()
            proc.terminate()
            pytest.skip(
                f"oa-agent healthz 不响应，跳过 bridge 集成测试；日志见 {log_path}"
            )
        yield OA_AGENT_BASE_URL
    finally:
        log_file.close()
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


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
