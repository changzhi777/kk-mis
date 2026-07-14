"""通知服务（webhook，新线索/订单提醒运营）

NOTIFY_WEBHOOK_URL 配企业微信/钉钉/Slack/自定义 webhook。
无配置时静默跳过（不阻塞业务）；失败静默（通知是非关键的旁路）。
"""
import os

import httpx

WEBHOOK_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")


async def notify(event: str, data: dict) -> None:
    """发 webhook 通知（POST {event, data}）。失败/无配置均静默。"""
    if not WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as cli:
            await cli.post(WEBHOOK_URL, json={"event": event, "data": data})
    except Exception:
        pass
