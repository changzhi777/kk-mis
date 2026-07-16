"""office 桥 httpx 封装 — admin → oa-agent /tools。

设计：
- OA_AGENT_URL 从 env 读取（与 oa_agent_bridge.py 一致，默认 127.0.0.1:9001），便于测试注入
- 不可达抛 OfficeBridgeUnavailable，路由层转 503
- oa-agent 对"工具不存在"返回 404、对工具内部错误返回 200+ok=False；本层统一规整
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

# oa-agent 服务地址（env 注入；测试用 monkeypatch.setenv 覆盖）
OA_AGENT_URL = os.environ.get("OA_AGENT_URL", "http://127.0.0.1:9001")
_TIMEOUT_LIST = 10.0
_TIMEOUT_INVOKE = 60.0

# 工具名白名单正则：只允许小写字母/数字/下划线；防止 `../health` 等路径注入到 URL
# （HIGH 10：invoke 拼 URL 前先校验，office.py /tools 调用层再叠 OFFICE_TOOLS 白名单）
_TOOL_NAME_RE = re.compile(r"^[a-z0-9_]+$")

# office 场景关心的 oa-agent 工具白名单：
# - health() 报告这些工具的可用情况
# - office.py /tools POST 端点用此集合做白名单校验（HIGH 9）
# 注意：`docx_to_html` + `merge_template` 是 office.py /preview + /merge 硬编码调用的
# 合法工具，必须包含，否则 /tools 透传时白名单会漏判
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
    "docx_to_html",
    "merge_template",
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
    - tool_name 非法（含路径分隔/点号等）→ ValueError
    - oa-agent 404（工具不存在）→ ok=False + error
    - oa-agent 200 + ok=False（工具内部错误）→ 透传
    - oa-agent 200 + ok=True → 透传

    **HIGH 10 修复**：在拼 URL 前对 tool_name 做正则白名单校验，防止
    `../health`、`/admin/..`、`%2e%2e` 等路径注入访问 oa-agent 非预期端点。
    调用方（office.py /tools）额外用 OFFICE_TOOLS 做语义白名单，本层只防注入。
    """
    if not isinstance(tool_name, str) or not _TOOL_NAME_RE.match(tool_name):
        # 不 raise HTTPException（service 层不该知道 HTTP），交由路由层翻译
        raise ValueError(
            f"非法 tool_name: {tool_name!r}（仅允许小写字母/数字/下划线）"
        )
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
