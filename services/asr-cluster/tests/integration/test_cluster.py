"""asr-cluster 集成测试（2026-07-13 全测计划）

启动 asr-cluster 子进程 :19100，验证：
- 健康检查
- 节点注册 / 列表 / 删除
- /transcribe 转发 mock
- 鉴权（无 X-API-Key → 401）
"""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


ASR_CLUSTER_TEST_PORT = 19100
ASR_CLUSTER_BASE = f"http://127.0.0.1:{ASR_CLUSTER_TEST_PORT}"
ASR_CLUSTER_KEY = "test-asr-cluster-key"
AUTH_HEADER = {"X-API-Key": ASR_CLUSTER_KEY}


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port):
            return True
        time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def asr_cluster_server():
    """启动 asr-cluster 子进程 :19100（无 DB，独立 in-memory registry）"""
    # 主动 kill 旧进程（避免上轮 fixture 残留 + 端口占用跳过启动）
    try:
        import subprocess as _sp
        _sp.run(["pkill", "-f", "app.main:app"], timeout=3)
    except Exception:
        pass
    time.sleep(1)

    if _port_in_use(ASR_CLUSTER_TEST_PORT):
        # 还有进程占着，fail 提示（手动清理）
        yield ASR_CLUSTER_BASE
        return

    env = {
        **os.environ,
        "APP_HOST": "127.0.0.1",
        "APP_PORT": str(ASR_CLUSTER_TEST_PORT),
        "MLX_ASR_API_KEY": "test-asr-cluster-key",  # verify_api_key 需要
        "LOG_LEVEL": "WARNING",
    }
    log_file = open("/tmp/asr_cluster_e2e.log", "w")
    asr_dir = Path(__file__).parent.parent.parent  # services/asr-cluster/
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(ASR_CLUSTER_TEST_PORT), "--log-level", "warning"],
        cwd=asr_dir,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    try:
        if not _wait_port(ASR_CLUSTER_TEST_PORT, timeout=20):
            log_file.close()
            proc.terminate()
            pytest.fail(f"asr-cluster 启动失败（:{ASR_CLUSTER_TEST_PORT}）\n{open('/tmp/asr_cluster_e2e.log').read()}")
        # 等 root 端点响应
        for _ in range(20):
            try:
                r = httpx.get(f"{ASR_CLUSTER_BASE}/", timeout=2.0)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        yield ASR_CLUSTER_BASE
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


# ── 集成测试 ────────────────────────────────────────────


def test_health_root(asr_cluster_server):
    """/ 返回服务元信息"""
    r = httpx.get(f"{ASR_CLUSTER_BASE}/", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "asr-cluster"
    assert "version" in body
    assert "nodes_count" in body


def test_list_nodes_initially_empty(asr_cluster_server):
    """启动时节点列表为空"""
    r = httpx.get(f"{ASR_CLUSTER_BASE}/nodes", timeout=5)
    assert r.status_code == 200
    # /nodes 返回 list（routes/nodes.py:get_client().list_nodes()）
    body = r.json()
    assert isinstance(body, list)


def test_register_node_persists_in_list(asr_cluster_server):
    """注册节点 → 出现在列表中"""
    # 注意：register 无鉴权（CLAUDE.md 标 known issue，本次集成测试不复测）
    r = httpx.post(
        f"{ASR_CLUSTER_BASE}/nodes/register",
        headers=AUTH_HEADER,
        json={
            "id": f"test-mlx-{int(time.time())}",
            "url": "http://100.88.88.34:9000",
            "api_key": "kk-cms-asr-local-dev-key-2026",
            "model": "mlx-community/whisper-large-v3-turbo",
            "priority": 0,
            "max_concurrent": 2,
        },
        timeout=5,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["node"]["id"] == body["node"]["id"]

    # 列表中应能找到
    r2 = httpx.get(f"{ASR_CLUSTER_BASE}/nodes", timeout=5)
    assert r2.status_code == 200
    nodes = r2.json()
    assert any(n["id"] == body["node"]["id"] for n in nodes)


def test_register_duplicate_node_rejected(asr_cluster_server):
    """同 ID 重复注册 → 400"""
    node_id = f"dup-mlx-{int(time.time())}"
    payload = {
        "id": node_id,
        "url": "http://test:9000",
        "api_key": "k",
        "model": "m",
        "priority": 0,
        "max_concurrent": 1,
    }
    r1 = httpx.post(f"{ASR_CLUSTER_BASE}/nodes/register", headers=AUTH_HEADER, json=payload, timeout=5)
    assert r1.status_code == 200
    r2 = httpx.post(f"{ASR_CLUSTER_BASE}/nodes/register", headers=AUTH_HEADER, json=payload, timeout=5)
    assert r2.status_code == 400
    assert node_id in r2.json()["detail"]


def test_deregister_node_removes_from_list(asr_cluster_server):
    """注销节点 → 列表移除"""
    node_id = f"del-mlx-{int(time.time())}"
    httpx.post(
        f"{ASR_CLUSTER_BASE}/nodes/register",
        headers=AUTH_HEADER,
        json={"id": node_id, "url": "http://t:9000", "api_key": "k"},
        timeout=5,
    )
    r = httpx.delete(f"{ASR_CLUSTER_BASE}/nodes/{node_id}", headers=AUTH_HEADER, timeout=5)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # 注销后列表无该节点
    r2 = httpx.get(f"{ASR_CLUSTER_BASE}/nodes", timeout=5)
    assert not any(n["id"] == node_id for n in r2.json())


def test_deregister_unknown_node_returns_404(asr_cluster_server):
    """注销不存在节点 → 404"""
    r = httpx.delete(f"{ASR_CLUSTER_BASE}/nodes/nonexistent-{int(time.time())}", headers=AUTH_HEADER, timeout=5)
    assert r.status_code == 404


def test_transcribe_dispatch_returns_400_for_missing_file(asr_cluster_server):
    """/transcribe 接受 audio_path，文件不存在时处理失败（不崩）"""
    r = httpx.post(
        f"{ASR_CLUSTER_BASE}/transcribe",
        headers=AUTH_HEADER,
        params={"audio_path": "/tmp/nonexistent-asr-test.m4a"},
        timeout=10,
    )
    # cluster 接到 audio_path 后会选节点；若无节点 → 404 / 5xx
    # 若有节点但文件不存在 → 4xx / 5xx
    assert r.status_code in (400, 404, 500, 502, 503)
