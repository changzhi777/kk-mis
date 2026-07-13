"""oa-agent 网关路由（透明反代到独立 oa-agent 服务）

oa-agent 是个独立 FastAPI 服务（独立仓库 ~/Documents/Claude/Projects/oa-agent/），
本路由只做 admin 内的网关注联：
- /admin/api/v1/oa-agent/healthz  →  oa-agent :9001/healthz
- /admin/api/v1/oa-agent/chat/sync → POST 转发
- /admin/api/v1/oa-agent/chat      → SSE 流式
- /admin/api/v1/oa-agent/skills    → 列 skill

注意：依赖 oa-agent 独立服务在 127.0.0.1:9001 跑着；未跑则路由 503。
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..deps import get_current_user
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oa-agent", tags=["oa-agent-bridge"])

# 决策 #3 重构（2026-07-13）：从 env 读取，便于测试/部署注入
# 默认 :9001（生产 oa-agent 端口）
import os

OA_AGENT_URL = os.environ.get("OA_AGENT_URL", "http://127.0.0.1:9001")
TIMEOUT_HEALTH = 5.0
TIMEOUT_CHAT = 300.0


@router.get("/healthz")
async def healthz():
    """检 oa-agent 是否在线。"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_HEALTH) as cli:
            r = await cli.get(f"{OA_AGENT_URL}/healthz")
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"oa-agent 不可达: {exc}",
        ) from exc


@router.post("/chat/sync")
async def chat_sync(req: Request, _user: User = Depends(get_current_user)):
    """同步转发到 oa-agent /chat/sync（要求已登录）。"""
    body = await req.json()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CHAT) as cli:
            r = await cli.post(f"{OA_AGENT_URL}/chat/sync", json=body)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"oa-agent 错误: {exc}") from exc


@router.post("/chat")
async def chat_stream(req: Request, _user: User = Depends(get_current_user)):
    """流式转发到 oa-agent /chat (SSE) — 要求已登录。"""

    body = await req.json()

    async def event_gen():
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_CHAT) as cli:
                async with cli.stream("POST", f"{OA_AGENT_URL}/chat", json=body) as r:
                    async for chunk in r.aiter_bytes():
                        if chunk:
                            yield chunk
        except Exception as exc:  # noqa: BLE001
            logger.warning("oa-agent stream error: %s", exc)
            yield b"event: error\ndata: " + str(exc).encode() + b"\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/skills")
async def list_skills(_user: User = Depends(get_current_user)):
    """列 oa-agent 已加载的 skills（透传）。"""
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(f"{OA_AGENT_URL}/skills")
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"oa-agent 不可达: {exc}") from exc


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    _user: User = Depends(get_current_user),
):
    """列最近 N 个 session（透传到 oa-agent /sessions）。"""
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(f"{OA_AGENT_URL}/sessions", params={"limit": limit})
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"oa-agent 不可达: {exc}") from exc


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """读指定 session 的 trace（透传到 oa-agent /sessions/{id}）。"""
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(f"{OA_AGENT_URL}/sessions/{session_id}")
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"oa-agent 不可达: {exc}") from exc
