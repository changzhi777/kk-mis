"""通知服务（webhook，新线索/订单提醒运营）

NOTIFY_WEBHOOK_URL 配企业微信/钉钉/Slack/自定义 webhook。
无配置时静默跳过（不阻塞业务）；通知是非关键的旁路。

MEDIUM 修复（2026-07-16）：
- client 复用（模块级连接池，原每次新建）
- raise_for_status（4xx/5xx 不当成功）
- 结构化失败日志（原 except: pass 静默吞错）
- 超时分离（connect 3s / read 5s，原固定 5s）
- URL 运行期读取（热加载，原 import 时冻结需重启）
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

# 模块级复用 client（连接池），懒初始化
_CLIENT: httpx.AsyncClient | None = None


def _webhook_url() -> str:
    """运行期读取（热加载，改 env 后下次调用即生效，无需重启进程）。"""
    return os.getenv("NOTIFY_WEBHOOK_URL", "")


async def _get_client() -> httpx.AsyncClient:
    """懒初始化模块级 client（连接池复用）。"""
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=3.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _CLIENT


async def notify(event: str, data: dict) -> None:
    """发 webhook 通知（POST {event, data}）。

    无配置静默跳过；失败记结构化日志（不阻塞业务，通知是旁路）。
    """
    url = _webhook_url()
    if not url:
        return
    try:
        cli = await _get_client()
        resp = await cli.post(url, json={"event": event, "data": data})
        resp.raise_for_status()  # 4xx/5xx 不当成功
    except Exception as exc:
        logger.warning(
            "notify 发送失败 event=%s err=%s:%s",
            event, type(exc).__name__, exc,
        )


async def close_client() -> None:
    """应用关闭时调用，释放连接池（main.py lifespan shutdown 挂接）。"""
    global _CLIENT
    if _CLIENT is not None:
        await _CLIENT.aclose()
        _CLIENT = None
