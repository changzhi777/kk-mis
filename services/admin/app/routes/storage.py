"""Storage 路由：前端直传 presign + 健康检查（Phase 2）

Phase 2 前端直传流程（仅 cos backend）：
1. 前端 POST /api/v1/storage/presign {filename, content_type, size} → {url, key, headers}
2. 前端 fetch(url, {method: PUT, body, headers}) → 直传 COS（省后端带宽）
3. 前端 POST /api/v1/cms/media/confirm {key, name, ...} → 落 MediaAsset（cms/media.py，待加）

local backend 不支持前端直传（presigned_upload 抛 NotImplementedError → 400 提示走中传）。
"""

import logging
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..deps import require_permission
from ..services.storage import ObjectKey, StorageError, get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/storage", tags=["storage"])

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".webm"}
MAX_SIZE_MB = 100


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    size: int  # 字节


class PresignResponse(BaseModel):
    url: str
    key: str
    method: str
    required_headers: dict[str, str]
    expires_at: str
    max_size: int


def _safe_filename(name: str) -> str:
    """提取 basename，去路径遍历（与 cms/media.py 一致）。"""
    base = Path(name or "file").name or "file"
    return base.replace("..", "").replace("/", "_").replace("\\", "_") or "file"


@router.post("/presign", response_model=PresignResponse)
async def presign_upload(
    body: PresignRequest,
    _=Depends(require_permission("cms:media:upload")),
):
    """申请前端直传 presigned PUT URL（仅 cos backend）。

    - 校验类型白名单 + 大小限（防滥用 presigned URL 传大文件/非法类型）
    - 生成 ObjectKey（uuid + safe filename），返给前端；前端 PUT 后用同 key 落账
    - local backend 抛 NotImplementedError → 400 提示走中转 upload
    """
    suffix = Path(body.filename).suffix.lower()
    if suffix not in ALLOWED_EXTS:
        raise HTTPException(400, f"不支持的文件类型: {suffix}")
    if body.size <= 0:
        raise HTTPException(400, "size 必须大于 0")
    if body.size > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"文件太大: {body.size / 1024 / 1024:.1f}MB > {MAX_SIZE_MB}MB")

    safe = _safe_filename(body.filename)
    key = ObjectKey(f"{uuid.uuid4().hex}_{safe}")

    storage = get_storage()
    try:
        p = await storage.presigned_upload(
            key,
            content_type=body.content_type,
            expires=timedelta(seconds=settings.cos_presign_expire or 3600),
        )
    except NotImplementedError as exc:
        raise HTTPException(
            400, "当前 storage backend 不支持前端直传，请走 /api/v1/cms/media/upload 中转"
        ) from exc
    except StorageError as exc:
        logger.exception("presign failed: %s", exc)
        raise HTTPException(500, f"签名失败: {exc}") from exc

    return PresignResponse(
        url=p.url,
        key=key.value,
        method=p.method,
        required_headers=dict(p.required_headers),
        expires_at=p.expires_at.isoformat(),
        max_size=p.max_size or 0,
    )


@router.get("/health")
async def storage_health():
    """查 storage backend 状态（公开，便于运维探测）。"""
    storage = get_storage()
    if hasattr(storage, "health"):
        return await storage.health()
    return {"backend": settings.storage_backend or "local"}
