"""TripGen 旅游攻略生成路由（方案 1：admin 内部库）

端点：
- POST /generate：接 Trip JSON → pipeline.generate → 返回可下载的 workspace key 列表
- GET  /download/{file_key}：下载生成产物（workspace 路径遏制，防目录遍历）
- POST /preview：接 Trip JSON → html_guide.render_html → 返回 HTML 字符串
- GET  /example：返回示例配置 JSON

交付闭环（2026-07-17，TRIPGEN-DELIVERY）：
- 产物落统一 OfficeWorkspace（``_tmp_tripgen_<uuid>`` 子目录），不再用 tempfile 泄露
  服务器绝对路径；``_tmp_`` 前缀让 workspace.cleanup() TTL 自动回收（默认 1h）。
- /generate 返回 workspace 相对 key（如 ``_tmp_tripgen_abc/xxx_图文攻略.html``），
  前端凭 key 调 /download 下载，无需感知服务器文件系统。
"""
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Any

from ..deps import require_permission
from ..services.tripgen import pipeline, config, html_guide
from ..services.tripgen.models import Trip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tripgen", tags=["行程攻略"])


class TripRequest(BaseModel):
    """Trip JSON 请求体（直接传 tripgen Trip 结构）。"""
    # 使用 model_config 允许任意字段（tripgen 的 dataclass 字段）
    model_config = {"extra": "allow"}
    title: str = ""
    subtitle: str = ""
    origin: str = ""
    party: str = ""
    dates: str = ""


class GenerateResponse(BaseModel):
    # 2026-07-17 起为 workspace 相对 key（可经 /download 下载），不再是服务器绝对路径
    files: list[str]
    count: int


def get_workspace(request: Request):
    """从 app.state 取统一 OfficeWorkspace；未就绪时 503。"""
    ws = getattr(request.app.state, "office_workspace", None)
    if ws is None:
        raise HTTPException(503, "workspace 未就绪")
    return ws


@router.get("/example")
async def get_example():
    """返回示例配置 JSON（供前端预填）。"""
    from ..services.tripgen.cli import EXAMPLE
    try:
        import yaml
        data = yaml.safe_load(EXAMPLE)
    except Exception:
        data = {"title": "示例行程", "party": "一大一小"}
    return data


@router.post("/preview")
async def preview_trip(
    body: dict[str, Any],
    _=Depends(require_permission("tripgen:generate")),
):
    """预览：接 Trip JSON → 返回图文攻略 HTML 字符串。"""
    try:
        trip = config.trip_from_dict(body)
    except Exception as e:
        raise HTTPException(400, f"行程数据解析失败: {e}")
    if not trip.title:
        raise HTTPException(400, "title 必填")
    # 生成临时 HTML
    html = html_guide.render_html(trip)
    return PlainTextResponse(html, media_type="text/html; charset=utf-8")


@router.post("/generate", response_model=GenerateResponse)
async def generate_trip(
    body: dict[str, Any],
    workspace=Depends(get_workspace),
    _=Depends(require_permission("tripgen:generate")),
):
    """生成 4 件套（正文PDF + 图文HTML + 图文PDF + 合并PDF）→ 返回可下载的 workspace key。"""
    try:
        trip = config.trip_from_dict(body)
    except Exception as e:
        raise HTTPException(400, f"行程数据解析失败: {e}")
    if not trip.title:
        raise HTTPException(400, "title 必填")

    # 任务级子目录：_tmp_ 前缀让 workspace.cleanup() TTL 自动清理
    job_dir = workspace.root / f"_tmp_tripgen_{uuid.uuid4().hex}"
    try:
        files_abs = pipeline.generate(trip, str(job_dir), log=logger.info)
    except Exception as e:
        logger.exception("tripgen 生成失败")
        raise HTTPException(500, f"生成失败: {e}")

    # 绝对路径 → workspace 相对 key（供 /download 消费；路径遏制由 download 端兜底）
    keys: list[str] = []
    for abs_path in files_abs:
        try:
            rel = os.path.relpath(abs_path, workspace.root)
        except ValueError:
            # Windows 跨盘符 relpath 抛 ValueError；生产 Linux/容器不会触发
            continue
        keys.append(rel.replace(os.sep, "/"))
    return GenerateResponse(files=keys, count=len(keys))


@router.get("/download/{file_key:path}")
async def download_trip_asset(
    file_key: str,
    workspace=Depends(get_workspace),
    _=Depends(require_permission("tripgen:generate")),
):
    """下载 tripgen 产物（workspace 路径遏制，防目录遍历；TTL 过期后 404）。"""
    try:
        target = workspace.resolve(file_key, must_exist=True)
    except FileNotFoundError:
        raise HTTPException(404, "文件不存在或已过期")
    except ValueError as e:
        # 路径逃出沙箱（.. / 绝对路径 / UNC）→ 400，不暴露内部细节
        raise HTTPException(400, f"非法路径: {e}")
    return FileResponse(
        str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )
