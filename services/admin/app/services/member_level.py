"""V3 会员等级自动升级（累计消费达门槛 → 升级）。

核销时 add_consumed 后调 check_and_upgrade_level：查 MemberStat.total_consumed，
找最高 min_consumed <= total_consumed 的启用等级，升级 level_id。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.member import MemberLevel, MemberStat


async def check_and_upgrade_level(session: AsyncSession, user_id: int) -> int | None:
    """检查并升级用户等级。

    返回新 level_id（发生升级）或 None（未升级 / 无 stat / 无匹配等级）。
    幂等：已是该等级不重复升级。
    """
    stat = (
        await session.execute(select(MemberStat).where(MemberStat.user_id == user_id))
    ).scalar_one_or_none()
    if not stat:
        return None
    # 找最高 min_consumed <= total_consumed 的启用等级（desc 取首条）
    target = (
        await session.execute(
            select(MemberLevel)
            .where(MemberLevel.status.is_(True), MemberLevel.min_consumed <= stat.total_consumed)
            .order_by(MemberLevel.min_consumed.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not target:
        return None
    if stat.level_id != target.id:
        stat.level_id = target.id
        await session.flush()
        return target.id
    return None
