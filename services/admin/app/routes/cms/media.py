"""CMS 素材库路由：上传/列表/删除 + 公开文件服务

2026-07-14 Sprint 0 改造：
- 上传通过 Storage 抽象层（默认 LocalStorage，Phase 1 切 CosStorage 零业务改动）
- 文件存储路径：{storage_local_root}/{storage_key.value}（如 storage/uploads/cms/media/abc.png）
- 读路径保留本地兼容（老 records.storage_backend='local' 走 FileResponse）
- 删：同步调用 Storage.delete()
"""

import logging
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
from ...services.storage import (
    ObjectKey,
    StorageError,
    UploadRequest,
    get_storage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cms/media", tags=["cms-media"])

# 兼容老的本地 serve_file 路径（基于 storage_backend='local' 且 storage_key=NULL 的记录）
LEGACY_UPLOAD_DIR = Path("storage/uploads")

ALLOWED_EXTS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "video": {".mp4", ".mov", ".webm"},
}
MAX_SIZE_MB = 100


def _safe_filename(name: str) -> str:
    """提取 basename，去路径遍历（../, /, \\）"""
    base = Path(name or "file").name or "file"
    return base.replace("..", "").replace("/", "_").replace("\\", "_") or "file"


@router.post("/upload", response_model=MediaAssetOut)
async def upload_media(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("cms:media:upload")),
):
    """上传素材（图/视频）→ 走 Storage 抽象层 → 返回 MediaAsset"""
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

    # ── Storage 写入 ──
    # Sprint 0 Phase：保留 Phase 0 写入的 stored_filename 直接作 ObjectKey（无 cms/media/ 前缀）
    # 这样 LocalStorage 物理路径 = storage/uploads/{stored_filename}，与原 FileResponse 路径一致
    safe = _safe_filename(file.filename or "file")
    stored_filename = f"{uuid.uuid4().hex}_{safe}"
    key = ObjectKey(stored_filename)

    storage = get_storage()
    try:
        result = await storage.put(
            UploadRequest(
                key=key,
                data=data,
                content_type=file.content_type or f"image/{suffix.lstrip('.')}",
                metadata={"uploaded_by": str(user.id)},
            )
        )
    except StorageError as exc:
        logger.exception("storage.put failed: %s", exc)
        raise HTTPException(500, f"上传失败: {exc}") from exc

    # ── URL 形态：local 走反代；cos 直接 cdn 域名（Phase 1 实现）──
    url = f"/admin/api/v1/cms/media/file/{stored_filename}"

    asset = MediaAsset(
        name=file.filename or stored_filename,
        type=media_type,
        url=url,
        size=len(data),
        uploaded_by=user.id,
        storage_backend="local",
        storage_key=key.value,
        etag=result.etag,
        content_type=file.content_type or f"image/{suffix.lstrip('.')}",
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return MediaAssetOut.model_validate(asset)


@router.get("/file/{filename}")
async def serve_file(filename: str):
    """公开访问素材文件（无需登录，前端 <img>/<video> src 用）

    Phase 0 仅支持 local backend（Storage backend 切 cos 后由 Phase 1 重定向到此路由逻辑调整）
    """
    safe = _safe_filename(filename)
    path = (LEGACY_UPLOAD_DIR / safe).resolve()
    if not str(path).startswith(str(LEGACY_UPLOAD_DIR.resolve())):
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
    """删素材：DB 记录 + 物理文件（统一走 Storage.delete）。"""
    a = await session.get(MediaAsset, media_id)
    if not a:
        raise HTTPException(404, "素材不存在")

    # 老数据兼容：URL 形态 /admin/api/v1/cms/media/file/{stored} → 从 URL 推 stored
    key = ObjectKey(a.storage_key) if a.storage_key else ObjectKey(
        _safe_filename(a.url.rsplit("/", 1)[-1])
    )
    try:
        await get_storage().delete(key)
    except StorageError as exc:
        logger.warning("storage.delete 失败（记录仍删）: %s", exc)

    await session.delete(a)
    await session.commit()
    return {"success": True}
