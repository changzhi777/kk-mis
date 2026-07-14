"""CMS 素材库路由：上传/列表/删除 + 公开文件服务

- 上传存 storage/uploads/{uuid}_{safe_name}（uuid 前缀防冲突 + 防路径遍历）
- 文件服务 GET /file/{filename} 公开（前端 <img src> 用，无需登录）
- 大小/类型校验（复用 meeting-notes 上传安全模式）
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import MediaAsset
from ...schemas.cms import MediaAssetOut

router = APIRouter(prefix="/api/v1/cms/media", tags=["cms-media"])

UPLOAD_DIR = Path("storage/uploads")
ALLOWED_EXTS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "video": {".mp4", ".mov", ".webm"},
}
MAX_SIZE_MB = 100


def _safe_filename(name: str) -> str:
    """提取 basename，去路径遍历（../, /, \\）"""
    base = os.path.basename(name) or "file"
    return base.replace("..", "").replace("/", "_").replace("\\", "_") or "file"


@router.post("/upload", response_model=MediaAssetOut)
async def upload_media(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("cms:media:upload")),
):
    """上传素材（图/视频）→ 返回 MediaAsset"""
    suffix = Path(file.filename or "file").suffix.lower()
    media_type = None
    for mtype, exts in ALLOWED_EXTS.items():
        if suffix in exts:
            media_type = mtype
            break
    if not media_type:
        raise HTTPException(400, f"不支持的文件类型: {suffix}")
    data = await file.read()
    size_mb = len(data) / 1024 / 1024
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(413, f"文件太大: {size_mb:.1f}MB > {MAX_SIZE_MB}MB")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}_{_safe_filename(file.filename or 'file')}"
    (UPLOAD_DIR / stored).write_bytes(data)
    asset = MediaAsset(
        name=file.filename or stored,
        type=media_type,
        url=f"/admin/api/v1/cms/media/file/{stored}",
        size=len(data),
        uploaded_by=user.id,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return MediaAssetOut.model_validate(asset)


@router.get("/file/{filename}")
async def serve_file(filename: str):
    """公开访问素材文件（无需登录，前端 <img>/<video> src 用）"""
    safe = _safe_filename(filename)
    path = (UPLOAD_DIR / safe).resolve()
    # 防路径遍历：确保在 UPLOAD_DIR 内
    if not str(path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(400, "非法路径")
    if not path.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path)


@router.get("")
async def list_media(
    type: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:media:list")),
):
    q = select(MediaAsset).order_by(MediaAsset.id.desc())
    if type:
        q = q.where(MediaAsset.type == type)
    items = (await session.execute(q)).scalars().all()
    return {"items": [MediaAssetOut.model_validate(a).model_dump() for a in items]}


@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:media:upload")),
):
    a = await session.get(MediaAsset, media_id)
    if not a:
        raise HTTPException(404, "素材不存在")
    try:
        stored = _safe_filename(a.url.rsplit("/", 1)[-1])
        path = UPLOAD_DIR / stored
        if path.is_file():
            path.unlink()
    except Exception:
        pass
    await session.delete(a)
    await session.commit()
    return {"success": True}
