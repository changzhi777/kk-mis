"""V2.0 经销商阶梯返点（M2.4 月结返余额）

月结：汇总经销商当月 activated 授权码消费额 → 阶梯算返点 → 返点入预付余额。
默认阶梯 R1/R2/R3（0-1万5% / 1-5万10% / 5万+15%）；合同 rebate_tiers 有值用合同档（M2.4 先默认）。
一个经销商一个月份一条（unique agent_id+period），已 settled 不可重复结算。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import Agent, User, V2ActivationCode, V2DealerBalance, V2RebateRecord
from ...schemas.v2.rebate import V2RebateRecordOut, V2RebateSettle
from ...utils import utcnow

router = APIRouter(prefix="/api/v2/dealer/rebate", tags=["v2-rebate"])

# 默认阶梯（合同 rebate_tiers 有值时改用合同档，M2.4 先默认占位）
# (tier, min_sales, max_sales, rebate_pct)
_DEFAULT_REBATE_TIERS = [
    ("R1", Decimal("0"), Decimal("10000"), Decimal("0.05")),
    ("R2", Decimal("10000"), Decimal("50000"), Decimal("0.10")),
    ("R3", Decimal("50000"), None, Decimal("0.15")),
]


def _apply_tier(total_sales: Decimal) -> tuple[str, Decimal]:
    """按累计销售额命中阶梯，返回 (tier, pct)。"""
    for tier, lo, hi, pct in _DEFAULT_REBATE_TIERS:
        if total_sales >= lo and (hi is None or total_sales < hi):
            return tier, pct
    return "R1", Decimal("0.05")


async def _get_my_agent(session: AsyncSession, user_id: int) -> Optional[Agent]:
    return (
        await session.execute(select(Agent).where(Agent.user_id == user_id))
    ).scalars().first()


async def _compute_monthly(
    session: AsyncSession, agent_id: int, year: int, month: int
) -> tuple[str, Decimal, str, Decimal, Decimal]:
    """汇总当月 activated 消费额 + 算返点。

    Python 端按 activated_at 月份筛（跨 SQLite/PG 方言，避免 extract 兼容问题）。
    返回 (period, total_sales, tier, pct, amount)。
    """
    period = f"{year:04d}-{month:02d}"
    codes = (
        await session.execute(
            select(V2ActivationCode).where(
                V2ActivationCode.agent_id == agent_id,
                V2ActivationCode.status == "activated",
            )
        )
    ).scalars().all()
    total = Decimal("0")
    for c in codes:
        if (
            c.activated_at
            and c.activated_at.year == year
            and c.activated_at.month == month
        ):
            total += c.price
    tier, pct = _apply_tier(total)
    amount = (total * pct).quantize(Decimal("0.01"))
    return period, total, tier, pct, amount


@router.get("", response_model=list[V2RebateRecordOut])
async def list_my_rebates(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商查自己返点记录（按 period 倒序）。"""
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    rows = (
        await session.execute(
            select(V2RebateRecord)
            .where(V2RebateRecord.agent_id == agent.id)
            .order_by(V2RebateRecord.period.desc())
        )
    ).scalars().all()
    return rows


@router.post("/settle", response_model=V2RebateRecordOut)
async def settle_my_rebate(
    req: V2RebateSettle,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """触发月结：汇总当月消费→算返点→返点入余额（已 settled 不可重复）。"""
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    today = date.today()
    year = req.year or today.year
    month = req.month or today.month

    period, total, tier, pct, amount = await _compute_monthly(
        session, agent.id, year, month
    )

    rec = (
        await session.execute(
            select(V2RebateRecord).where(
                V2RebateRecord.agent_id == agent.id,
                V2RebateRecord.period == period,
            )
        )
    ).scalars().first()
    if rec and rec.status == "settled":
        raise HTTPException(409, f"{period} 已结算，不可重复")

    if not rec:
        rec = V2RebateRecord(
            agent_id=agent.id,
            period=period,
            total_sales=total,
            tier=tier,
            rebate_pct=pct,
            rebate_amount=amount,
            status="pending",
        )
        session.add(rec)
    else:
        rec.total_sales = total
        rec.tier = tier
        rec.rebate_pct = pct
        rec.rebate_amount = amount
    await session.flush()

    # 返点入预付余额（锁行）
    bal = (
        await session.execute(
            select(V2DealerBalance)
            .where(V2DealerBalance.agent_id == agent.id)
            .with_for_update()
        )
    ).scalars().first()
    if not bal:
        raise HTTPException(500, "余额账户缺失")
    bal.balance += amount
    rec.status = "settled"
    rec.settled_at = utcnow()
    await session.commit()
    await session.refresh(rec)
    return rec
