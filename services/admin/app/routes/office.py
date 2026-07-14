"""office 路由 — admin 文档处理桥（转发 oa-agent 工具，绕过 LLM）。

端点：
- GET  /api/v1/office/health      探测 oa-agent + 报告 office 工具可用性
- GET  /api/v1/office/tools       透传 oa-agent GET /tools（列所有工具）
- POST /api/v1/office/tools       透传：body {tool, args} → oa-agent POST /tools/{tool}
- POST /api/v1/office/read        便捷读：body {format, path} → read_docx/pdf/md/excel_read
- GET  /api/v1/office/preview/{id} 🔜 501（待 oa-agent 扩展 docx→html/图渲染）
- POST /api/v1/office/merge       🔜 501（待模板合并）

所有端点要求登录（get_current_user）。oa-agent 不可达 → 503。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_user
from ..models import User
from ..services.office import bridge
from ..services.office.bridge import OfficeBridgeUnavailable

router = APIRouter(prefix="/api/v1/office", tags=["office"])

# format → oa-agent read 工具名
_READ_TOOL: dict[str, str] = {
    "docx": "read_docx",
    "pdf": "read_pdf",
    "md": "read_md",
    "markdown": "read_md",
    "excel": "excel_read",
    "xlsx": "excel_read",
}


class ToolCallRequest(BaseModel):
    tool: str = Field(..., description="oa-agent 工具名，如 read_docx / excel_write")
    args: dict[str, Any] = Field(default_factory=dict, description="工具参数（按签名）")
    session_id: str | None = Field(None, description="可选 audit 上下文")


class ReadRequest(BaseModel):
    format: str = Field("docx", description="docx|pdf|md|excel")
    path: str = Field(..., description="文件路径（oa-agent workspace 内）")


class MergeRequest(BaseModel):
    template: str = Field(..., description="含 {{ var }} 占位的 docx 模板路径（oa-agent workspace 内）")
    output: str = Field(..., description="输出 docx 路径（oa-agent workspace 内）")
    context: dict[str, Any] = Field(default_factory=dict, description="变量填充字典")


@router.get("/health")
async def health(_user: User = Depends(get_current_user)):
    """探测 oa-agent 可达性 + office 工具可用情况。"""
    return await bridge.health()


@router.get("/tools")
async def list_tools(_user: User = Depends(get_current_user)):
    """透传 oa-agent GET /tools（列所有已注册工具）。"""
    try:
        return await bridge.list_tools()
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.post("/tools")
async def call_tool(req: ToolCallRequest, _user: User = Depends(get_current_user)):
    """透传：直接调 oa-agent 任意工具（POST /tools/{tool}）。"""
    try:
        return await bridge.invoke(req.tool, req.args, session_id=req.session_id)
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.post("/read")
async def read(req: ReadRequest, _user: User = Depends(get_current_user)):
    """便捷读：按 format 选 read_* 工具，传 path。"""
    fmt = req.format.lower()
    tool = _READ_TOOL.get(fmt)
    if not tool:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 format: {req.format}（支持 docx/pdf/md/excel）",
        )
    try:
        return await bridge.invoke(tool, {"path": req.path})
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.get("/preview")
async def preview(path: str, _user: User = Depends(get_current_user)):
    """docx → HTML 预览（转发 oa-agent docx_to_html，mammoth 渲染）。"""
    try:
        return await bridge.invoke("docx_to_html", {"path": path})
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.post("/merge")
async def merge(req: MergeRequest, _user: User = Depends(get_current_user)):
    """docx 模板变量填充合并（转发 oa-agent merge_template，docxtpl 渲染）。

    用于订单数据 → 合同等场景。
    """
    try:
        return await bridge.invoke(
            "merge_template",
            {"template": req.template, "output": req.output, "variables": req.context},
        )
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc
