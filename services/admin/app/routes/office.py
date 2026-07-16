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

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..deps import get_current_user, require_permission
from ..models import User
from ..services.office import bridge
from ..services.office.bridge import OFFICE_TOOLS, OfficeBridgeUnavailable
from ..services.office.engine import OfficeEngineError, batch_process, data_to_excel, docx_to_pdf, fill_form, html_to_pdf, template_to_pptx

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


def _safe_path(p: str, field: str = "path") -> str:
    """路径遏制（HIGH 8）：拒绝绝对路径 + 拒绝含 `..` 的遍历输入。

    oa-agent 侧的 workspace 沙箱由它自己管，admin 侧只负责拦截恶意输入，
    不让任意登录用户借 office 桥读 `/etc/passwd` 或覆盖任意 docx。

    允许：workspace 内的相对路径（如 ``docs/a.docx``、``sub/b.pdf``）。
    拒绝：
      - 空字符串 / None
      - POSIX 绝对路径（``/etc/passwd``）
      - Windows 绝对路径（``C:\\Windows\\win.ini``、``C:/x``）
      - 含 ``..`` 段的遍历路径（``a/../../b``、``..`` 、``../secret``）
      - UNC 路径（``\\\\server\\share``）
    """
    if not p or not isinstance(p, str):
        raise HTTPException(status_code=400, detail=f"{field} 不能为空")
    # UNC \\server\c$ 或 \\\\server 风格
    if p.startswith("\\\\"):
        raise HTTPException(status_code=400, detail=f"{field} 不允许 UNC 路径: {p!r}")
    # POSIX 绝对 / Windows 盘符（C:\、C:/）
    if p.startswith("/") or (len(p) >= 2 and p[1] == ":" and p[0].isalpha()):
        raise HTTPException(status_code=400, detail=f"{field} 不允许绝对路径: {p!r}")
    # 统一斜杠后按段切分，任一段为 .. 即拒
    parts = p.replace("\\", "/").split("/")
    if any(seg == ".." for seg in parts):
        raise HTTPException(status_code=400, detail=f"{field} 不允许包含 '..': {p!r}")
    return p


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
async def call_tool(
    req: ToolCallRequest,
    _user: User = Depends(require_permission("office:tool:invoke")),
):
    """透传：直接调 oa-agent 任意工具（POST /tools/{tool}）。

    **HIGH 9 修复**：
    - 路由从 ``get_current_user`` 升级为 ``require_permission("office:tool:invoke")``，
      任意登录用户不再能调任意工具；
    - ``req.tool`` 必须在 ``OFFICE_TOOLS`` 白名单内，防止越权调用 oa-agent 其他工具
      （如 query_weather、AI 设计行程等非 office 场景工具）；
    - ``bridge.invoke`` 会再叠一层正则校验（HIGH 10），防止 URL 路径注入。
    """
    if req.tool not in OFFICE_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"tool 不在 office 白名单内: {req.tool!r}（允许: {sorted(OFFICE_TOOLS)}）",
        )
    try:
        return await bridge.invoke(req.tool, req.args, session_id=req.session_id)
    except ValueError as exc:
        # bridge.invoke 正则校验失败（理论上 OFFICE_TOOLS 已挡住，这里是纵深防御）
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.post("/read")
async def read(req: ReadRequest, _user: User = Depends(get_current_user)):
    """便捷读：按 format 选 read_* 工具，传 path。

    **HIGH 8 修复**：path 经 ``_safe_path`` 拦截绝对路径 + `..` 遍历，
    防止任意登录用户读 `/etc/passwd` 等 oa-agent workspace 外文件。
    """
    fmt = req.format.lower()
    tool = _READ_TOOL.get(fmt)
    if not tool:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 format: {req.format}（支持 docx/pdf/md/excel）",
        )
    safe_path = _safe_path(req.path)
    try:
        return await bridge.invoke(tool, {"path": safe_path})
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.get("/preview")
async def preview(path: str, _user: User = Depends(get_current_user)):
    """docx → HTML 预览（转发 oa-agent docx_to_html，mammoth 渲染）。

    **HIGH 8 修复**：path 经 ``_safe_path`` 校验后再透传。
    """
    safe_path = _safe_path(path)
    try:
        return await bridge.invoke("docx_to_html", {"path": safe_path})
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


@router.post("/merge")
async def merge(req: MergeRequest, _user: User = Depends(get_current_user)):
    """docx 模板变量填充合并（转发 oa-agent merge_template，docxtpl 渲染）。

    用于订单数据 → 合同等场景。

    **HIGH 8 修复**：template + output 均经 ``_safe_path`` 校验，
    防止任意登录用户覆盖 oa-agent workspace 外的任意 docx。
    """
    safe_template = _safe_path(req.template, field="template")
    safe_output = _safe_path(req.output, field="output")
    try:
        return await bridge.invoke(
            "merge_template",
            {"template": safe_template, "output": safe_output, "variables": req.context},
        )
    except OfficeBridgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"oa-agent 不可达: {exc}") from exc


# ── Sprint 2：本地引擎直接处理端点（不依赖 oa-agent，engine.py 实装） ────────
# 端点 1-5 全部要求 office:tool:invoke 权限（同 B2 修复后的权限码），
# 统一用 FileResponse 回传生成文件，OfficeEngineError → HTTP 400。
# 异步路由包装同步 engine 函数，避免阻塞事件循环。


class ExcelRequest(BaseModel):
    data: list[Any] = Field(..., description="二维数组或 dict 列表")
    headers: list[str] | None = Field(None, description="可选表头（list[list] 时生效）")
    sheet_name: str = Field("Sheet1", description="工作表名")


class PptxRequest(BaseModel):
    slides: list[dict[str, Any]] = Field(..., description="[{title, content, layout?}]")
    template: str | None = Field(None, description="可选 pptx 模板路径（服务端本地路径）")


class BatchRequest(BaseModel):
    input_dir: str = Field(..., description="输入目录（服务端本地路径）")
    operation: str = Field(..., description="pdf | form | copy")
    output_dir: str | None = Field(None, description="输出目录，缺省在 input_dir 下生成 output_<op>")
    pattern: str = Field("*", description="glob 匹配模式")


@router.post("/pdf")
async def to_pdf(
    file: UploadFile = File(...),
    _user: User = Depends(require_permission("office:tool:invoke")),
):
    """上传 docx/html 文件 → PDF。

    按上传文件后缀分流：.docx 走 mammoth + weasyprint；.html/.htm 读取后直接 weasyprint。
    其他扩展名一律 400。
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".docx", ".html", ".htm"}:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {suffix!r}（仅支持 .docx / .html）",
        )
    raw = await file.read()
    tmp_src = Path(tempfile.mkstemp(suffix=suffix)[1])
    tmp_src.write_bytes(raw)
    out_pdf = tmp_src.with_suffix(".pdf")
    try:
        if suffix == ".docx":
            docx_to_pdf(tmp_src, out_pdf)
        else:
            html_to_pdf(raw.decode("utf-8", errors="replace"), out_pdf)
    except OfficeEngineError as exc:
        raise HTTPException(status_code=400, detail=f"PDF 转换失败: {exc}") from exc
    return FileResponse(
        path=str(out_pdf),
        media_type="application/pdf",
        filename=(Path(file.filename or "converted").stem or "converted") + ".pdf",
    )


@router.post("/excel")
async def to_excel(
    req: ExcelRequest,
    _user: User = Depends(require_permission("office:tool:invoke")),
):
    """JSON 数据 → xlsx（openpyxl）。"""
    out = Path(tempfile.mkstemp(suffix=".xlsx")[1])
    try:
        data_to_excel(req.data, out, headers=req.headers, sheet_name=req.sheet_name)
    except OfficeEngineError as exc:
        raise HTTPException(status_code=400, detail=f"Excel 生成失败: {exc}") from exc
    return FileResponse(path=str(out), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="data.xlsx")


@router.post("/pptx")
async def to_pptx(
    req: PptxRequest,
    _user: User = Depends(require_permission("office:tool:invoke")),
):
    """JSON slides → pptx（python-pptx）。"""
    out = Path(tempfile.mkstemp(suffix=".pptx")[1])
    try:
        template_path = req.template if req.template else None
        template_to_pptx(req.slides, out, template=template_path)
    except OfficeEngineError as exc:
        raise HTTPException(status_code=400, detail=f"PPT 生成失败: {exc}") from exc
    return FileResponse(path=str(out), media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename="report.pptx")


@router.post("/form")
async def fill_form_endpoint(
    file: UploadFile = File(..., description="含 {{ var }} 占位的 docx 模板"),
    data: str = Form(..., description="JSON 字符串变量字典，如 {\"party_a\":\"大华天麓\"}"),
    _user: User = Depends(require_permission("office:tool:invoke")),
):
    """上传 docx 模板 + JSON 变量 → 填充后 docx（docxtpl）。"""
    try:
        variables: dict[str, Any] = json.loads(data)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"data 非合法 JSON: {exc}") from exc
    if not isinstance(variables, dict):
        raise HTTPException(status_code=400, detail="data 必须是 JSON 对象")

    raw = await file.read()
    tmp_tpl = Path(tempfile.mkstemp(suffix=".docx")[1])
    tmp_tpl.write_bytes(raw)
    out = tmp_tpl.with_name(f"{tmp_tpl.stem}_filled.docx")
    try:
        fill_form(tmp_tpl, variables, out)
    except OfficeEngineError as exc:
        raise HTTPException(status_code=400, detail=f"表单填充失败: {exc}") from exc
    return FileResponse(
        path=str(out),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=(Path(file.filename or "filled").stem or "filled") + "_filled.docx",
    )


@router.post("/batch")
async def batch_endpoint(
    req: BatchRequest,
    _user: User = Depends(require_permission("office:tool:invoke")),
):
    """文件夹批量处理（pdf/form/copy），返回处理结果路径列表。"""
    try:
        results = await batch_process(
            input_dir=req.input_dir,
            operation=req.operation,
            output_dir=req.output_dir,
            pattern=req.pattern,
        )
    except OfficeEngineError as exc:
        raise HTTPException(status_code=400, detail=f"批量处理失败: {exc}") from exc
    return {
        "operation": req.operation,
        "input_dir": req.input_dir,
        "output_dir": str(req.output_dir or Path(req.input_dir) / f"output_{req.operation}"),
        "processed": [str(p) for p in results],
        "count": len(results),
    }
