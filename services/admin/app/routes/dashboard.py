"""工作台（聚合待办 + 快捷 count + 最新公告 + 个人 OA 概况）"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user
from ..models import (
    AgentOrder,
    Announcement,
    ApprovalInstance,
    AssetCard,
    Attendance,
    ExpenseRequest,
    User,
    WorkReport,
)

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
    """聚合待办 + 各模块 count + 个人 OA 概况 + 最新公告"""
    asset_draft = await _count(
        session, select(AssetCard).where(AssetCard.status == "draft")
    )
    order_pending = await _count(
        session, select(AgentOrder).where(AgentOrder.status == "pending")
    )
    announcement_count = await _count(
        session, select(Announcement).where(Announcement.status == "published")
    )
    pending_approvals = await _count(
        session, select(ApprovalInstance).where(ApprovalInstance.status == "pending")
    )

    latest = (
        await session.execute(
            select(Announcement)
            .where(Announcement.status == "published")
            .order_by(Announcement.published_at.desc())
            .limit(5)
        )
    ).scalars().all()

    # 个人 OA 概况
    today = date.today()
    my_att = (
        await session.execute(
            select(Attendance).where(
                Attendance.user_id == user.id, Attendance.date == today
            )
        )
    ).scalar_one_or_none()
    month_expense = (
        await session.execute(
            select(func.coalesce(func.sum(ExpenseRequest.amount), 0)).where(
                ExpenseRequest.user_id == user.id,
                ExpenseRequest.status == "approved",
                extract("year", ExpenseRequest.created_at) == today.year,
                extract("month", ExpenseRequest.created_at) == today.month,
            )
        )
    ).scalar_one()
    my_report_count = await _count(
        session, select(WorkReport).where(WorkReport.user_id == user.id)
    )

    return {
        "todos": [
            {"type": "asset_draft", "label": "卡券待发放", "count": asset_draft, "link": "/asset/card"},
            {"type": "order_pending", "label": "订单待付款", "count": order_pending, "link": "/agent/order"},
            {"type": "pending_approvals", "label": "待审批", "count": pending_approvals, "link": "/approval"},
        ],
        "counts": {"announcements": announcement_count},
        "me": {
            "clock_in": my_att.clock_in.isoformat() if my_att and my_att.clock_in else None,
            "clock_out": my_att.clock_out.isoformat() if my_att and my_att.clock_out else None,
            "attendance_status": my_att.status if my_att else None,
            "month_expense": float(month_expense),
            "report_count": my_report_count,
        },
        "latest_announcements": [
            {
                "id": a.id,
                "title": a.title,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            }
            for a in latest
        ],
    }
