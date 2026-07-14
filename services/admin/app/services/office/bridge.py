"""office 桥 httpx 封装 — admin → oa-agent /tools。

设计：
- OA_AGENT_URL 从 env 读取（与 oa_agent_bridge.py 一致，默认 127.0.0.1:9001），便于测试注入
- 不可达抛 OfficeBridgeUnavailable，路由层转 503
- oa-agent 对"工具不存在"返回 404、对工具内部错误返回 200+ok=False；本层统一规整
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# oa-agent 服务地址（env 注入；测试用 monkeypatch.setenv 覆盖）
OA_AGENT_URL = os.environ.get("OA_AGENT_URL", "http://127.0.0.1:9001")
_TIMEOUT_LIST = 10.0
_TIMEOUT_INVOKE = 60.0

# office 场景关心的 oa-agent 工具白名单（health 报告用）
OFFICE_TOOLS = [
    "read_md",
    "read_pdf",
    "read_docx",
    "excel_read",
    "excel_list_sheets",
    "write_md",
    "write_pdf",
    "write_docx",
    "excel_write",
]


class OfficeBridgeUnavailable(RuntimeError):
    """oa-agent 不可达或响应异常。"""


async def list_tools(source: str | None = None) -> dict[str, Any]:
    """GET oa-agent /tools — 列已注册工具。"""
    params: dict[str, str] = {}
    if source:
        params["source"] = source
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_LIST) as cli:
            r = await cli.get(f"{OA_AGENT_URL}/tools", params=params)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, OSError) as exc:
        raise OfficeBridgeUnavailable(str(exc)) from exc


async def invoke(
    tool_name: str,
    args: dict[str, Any],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """POST oa-agent /tools/{name} — 直接调用工具（绕过 LLM）。

    返回规整后的 ``{tool, ok, error, result}``：
    - oa-agent 404（工具不存在）→ ok=False + error
    - oa-agent 200 + ok=False（工具内部错误）→ 透传
    - oa-agent 200 + ok=True → 透传
    """
    payload: dict[str, Any] = {"args": args}
    if session_id:
        payload["session_id"] = session_id
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_INVOKE) as cli:
            r = await cli.post(f"{OA_AGENT_URL}/tools/{tool_name}", json=payload)
    except (httpx.HTTPError, OSError) as exc:
        raise OfficeBridgeUnavailable(str(exc)) from exc
    if r.status_code == 404:
        return {
            "tool": tool_name,
            "ok": False,
            "error": f"tool '{tool_name}' not found in oa-agent",
            "result": None,
        }
    return r.json()


async def health() -> dict[str, Any]:
    """探测 oa-agent 可达性 + 报告 office 相关工具可用情况。"""
    try:
        tools = await list_tools()
    except OfficeBridgeUnavailable as exc:
        return {
            "ok": False,
            "oa_agent_url": OA_AGENT_URL,
            "error": str(exc),
            "office_tools": [],
            "total_tools": 0,
        }
    names = {t["name"] for t in tools.get("tools", [])}
    return {
        "ok": True,
        "oa_agent_url": OA_AGENT_URL,
        "total_tools": tools.get("count", 0),
        "office_tools": sorted(names & set(OFFICE_TOOLS)),
    }
