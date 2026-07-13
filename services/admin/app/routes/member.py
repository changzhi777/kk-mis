"""会员积分 + 等级端点（V2 积分 / V3 等级，2026-07-13）

- GET  /api/v1/me/points        — 我的积分余额
- GET  /api/v1/me/points/log    — 积分流水
- GET  /api/v1/me/level         — 我的会员等级 + 权益 + 下一级进度（V3）
- GET  /api/v1/admin/member-levels — 会员等级列表（admin，V3）
- POST /api/v1/admin/points/adjust — admin 手动调积分
"""
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user, require_permission
from ..models import MemberLevel, PointsLog, User
from ..services.points import award_points, get_or_create_stat, upgrade_level

router = APIRouter(prefix="/api/v1", tags=["member-points"])


@router.get("/me/points")
async def my_points(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stat = await get_or_create_stat(user.id, session)
    return {
        "points_balance": stat.points_balance,
        "frozen_points": stat.frozen_points,
        "total_consumed": float(stat.total_consumed or 0),
        "level_id": stat.level_id,
    }


@router.get("/me/points/log")
async def my_points_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(PointsLog)
        .where(PointsLog.user_id == user.id)
        .order_by(PointsLog.id.desc())
    )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {
        "items": [
            {
                "id": l.id,
                "delta": l.delta,
                "balance_after": l.balance_after,
                "reason": l.reason,
                "ref_type": l.ref_type,
                "ref_id": l.ref_id,
                "remark": l.remark,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in items
        ],
        "total": total,
    }


@router.get("/me/level")
async def my_level(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """V3 我的会员等级 + 权益 + 下一级进度（触发自动升级判定）"""
    stat = await upgrade_level(user.id, session)  # 触发升级判定
    level = await session.get(MemberLevel, stat.level_id) if stat.level_id else None
    next_level = None
    if level:
        next_level = (
            await session.execute(
                select(MemberLevel)
                .where(
                    MemberLevel.status.is_(True),
                    MemberLevel.min_consumed > (level.min_consumed or 0),
                )
                .order_by(MemberLevel.min_consumed.asc())
            )
        ).scalars().first()
    return {
        "level": (
            {"id": level.id, "name": level.name, "discount": float(level.discount)}
            if level else None
        ),
        "total_consumed": float(stat.total_consumed or 0),
        "points_balance": stat.points_balance,
        "next_level": (
            {
                "name": next_level.name,
                "min_consumed": float(next_level.min_consumed or 0),
                "gap": float((next_level.min_consumed or 0) - (stat.total_consumed or 0)),
            }
            if next_level else None
        ),
    }


@router.get("/admin/member-levels")
async def list_member_levels(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:save")),
):
    """V3 会员等级列表（admin）"""
    levels = (
        await session.execute(select(MemberLevel).order_by(MemberLevel.sort))
    ).scalars().all()
    return {
        "items": [
            {
                "id": l.id,
                "name": l.name,
                "min_consumed": float(l.min_consumed or 0),
                "discount": float(l.discount),
                "sort": l.sort,
                "status": l.status,
            }
            for l in levels
        ]
    }


@router.post("/admin/points/adjust")
async def adjust_points(
    user_id: int = Body(..., embed=True),
    delta: int = Body(..., embed=True),
    reason: str = Body("admin_adjust", embed=True),
    remark: str = Body(None, embed=True),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:save")),  # 复用用户管理权限
):
    """admin 手动调整积分（正加负扣）"""
    await award_points(user_id, delta, reason, session, ref_type="admin", remark=remark)
    stat = await get_or_create_stat(user_id, session)
    await session.commit()
    return {"success": True, "balance": stat.points_balance}
