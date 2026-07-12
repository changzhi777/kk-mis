"""公告管理（CRUD + 发布/归档 + scope 定向）"""
from ...utils import utcnow
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, require_permission
from ...models import Announcement, User
from ...schemas.oa import AnnouncementCreate, AnnouncementOut

router = APIRouter(prefix="/api/v1/oa/announcements", tags=["oa-announcement"])


@router.get("")
async def list_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    stmt = select(Announcement)
    if status:
        stmt = stmt.where(Announcement.status == status)
    # scope 定向：全员公告 + 本部门公告
    stmt = stmt.where(
        or_(Announcement.scope == "all", Announcement.dept_id == user.dept_id)
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(
            stmt.order_by(Announcement.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [AnnouncementOut.model_validate(a).model_dump() for a in items],
        "total": total,
    }


@router.post("", response_model=AnnouncementOut)
async def create_announcement(
    req: AnnouncementCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("oa:announcement:save")),
):
    a = Announcement(**req.model_dump(), publisher_id=user.id)
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return AnnouncementOut.model_validate(a)


@router.get("/{aid}", response_model=AnnouncementOut)
async def get_announcement(
    aid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    a = await session.get(Announcement, aid)
    if not a:
        raise HTTPException(404, "公告不存在")
    return AnnouncementOut.model_validate(a)


@router.post("/{aid}/publish", response_model=AnnouncementOut)
async def publish_announcement(
    aid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:announcement:save")),
):
    a = await session.get(Announcement, aid)
    if not a:
        raise HTTPException(404, "公告不存在")
    a.status = "published"
    a.published_at = utcnow()
    await session.commit()
    await session.refresh(a)
    return AnnouncementOut.model_validate(a)


@router.post("/{aid}/archive", response_model=AnnouncementOut)
async def archive_announcement(
    aid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:announcement:save")),
):
    a = await session.get(Announcement, aid)
    if not a:
        raise HTTPException(404, "公告不存在")
    a.status = "archived"
    await session.commit()
    await session.refresh(a)
    return AnnouncementOut.model_validate(a)


@router.delete("/{aid}")
async def delete_announcement(
    aid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:announcement:save")),
):
    a = await session.get(Announcement, aid)
    if not a:
        raise HTTPException(404, "公告不存在")
    await session.delete(a)
    await session.commit()
    return {"success": True}
