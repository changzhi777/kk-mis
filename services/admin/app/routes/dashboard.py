"""工作台（聚合待办 + 快捷 count + 最新公告）"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user
from ..models import AgentOrder, Announcement, AssetCard, User

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


async def _count(session: AsyncSession, stmt) -> int:
    return (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()


@router.get("")
async def dashboard(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """聚合待办 + 各模块 count + 最新公告"""
    asset_draft = await _count(
        session, select(AssetCard).where(AssetCard.status == "draft")
    )
    order_pending = await _count(
        session, select(AgentOrder).where(AgentOrder.status == "pending")
    )
    announcement_count = await _count(
        session, select(Announcement).where(Announcement.status == "published")
    )
    latest = (
        await session.execute(
            select(Announcement)
            .where(Announcement.status == "published")
            .order_by(Announcement.published_at.desc())
            .limit(5)
        )
    ).scalars().all()

    return {
        "todos": [
            {"type": "asset_draft", "label": "卡券待发放", "count": asset_draft, "link": "/asset/card"},
            {"type": "order_pending", "label": "订单待付款", "count": order_pending, "link": "/agent/order"},
        ],
        "counts": {"announcements": announcement_count},
        "latest_announcements": [
            {
                "id": a.id,
                "title": a.title,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            }
            for a in latest
        ],
    }
