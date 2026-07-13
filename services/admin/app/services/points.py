"""积分服务（V2/V3，2026-07-13）：加分 + 流水 + 余额 + 累计消费 + 自动升级。

V3：add_consumed 后调 upgrade_level（按 total_consumed 自动升到最高满足门槛的等级）。
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MemberLevel, MemberStat, PointsLog


async def get_or_create_stat(user_id: int, session: AsyncSession) -> MemberStat:
    """获取或创建会员档案（首次访问懒建）"""
    stat = (
        await session.execute(select(MemberStat).where(MemberStat.user_id == user_id))
    ).scalar_one_or_none()
    if not stat:
        stat = MemberStat(user_id=user_id, points_balance=0, total_consumed=0)
        session.add(stat)
        await session.flush()
    return stat


async def award_points(
    user_id: int,
    delta: int,
    reason: str,
    session: AsyncSession,
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
    remark: Optional[str] = None,
) -> MemberStat:
    """加分（delta 可负=扣减）。更新余额 + 写流水（balance_after 审计）。"""
    if delta == 0:
        return await get_or_create_stat(user_id, session)
    stat = await get_or_create_stat(user_id, session)
    stat.points_balance = (stat.points_balance or 0) + delta
    session.add(
        PointsLog(
            user_id=user_id,
            delta=delta,
            balance_after=stat.points_balance,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            remark=remark,
        )
    )
    return stat


async def upgrade_level(user_id: int, session: AsyncSession) -> MemberStat:
    """V3 根据 total_consumed 自动升级到最高满足门槛的等级。"""
    stat = await get_or_create_stat(user_id, session)
    levels = (
        await session.execute(
            select(MemberLevel)
            .where(MemberLevel.status.is_(True))
            .order_by(MemberLevel.min_consumed.desc())
        )
    ).scalars().all()
    target = None
    for lvl in levels:
        if (stat.total_consumed or 0) >= (lvl.min_consumed or 0):
            target = lvl
            break
    if target and stat.level_id != target.id:
        stat.level_id = target.id  # 自动升级（只升不降，累计消费不回退）
    return stat


async def add_consumed(user_id: int, amount: Decimal, session: AsyncSession) -> MemberStat:
    """累计消费（V3 升级依据，核销/订单完成时调）+ 自动升级判定。"""
    stat = await get_or_create_stat(user_id, session)
    stat.total_consumed = (stat.total_consumed or 0) + (amount or 0)
    await upgrade_level(user_id, session)  # V3 累计后自动升级
    return stat
