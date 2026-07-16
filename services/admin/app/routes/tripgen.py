"""TripGen 旅游攻略生成路由（方案 1：admin 内部库）

端点：
- POST /generate：接 Trip JSON → pipeline.generate → 返回生成文件列表
- POST /preview：接 Trip JSON → html_guide.write_html → 返回 HTML 字符串
- GET  /example：返回示例配置 JSON
"""
import logging
import tempfile
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
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
    files: list[str]
    count: int


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
    _=Depends(require_permission("tripgen:generate")),
):
    """生成 4 件套（正文PDF + 图文HTML + 图文PDF + 合并PDF）→ 返回文件路径。"""
    try:
        trip = config.trip_from_dict(body)
    except Exception as e:
        raise HTTPException(400, f"行程数据解析失败: {e}")
    if not trip.title:
        raise HTTPException(400, "title 必填")
    # 生成到临时目录
    out_dir = tempfile.mkdtemp(prefix="tripgen_")
    try:
        files = pipeline.generate(trip, out_dir, log=logger.info)
    except Exception as e:
        logger.exception("tripgen 生成失败")
        raise HTTPException(500, f"生成失败: {e}")
    return GenerateResponse(files=files, count=len(files))
