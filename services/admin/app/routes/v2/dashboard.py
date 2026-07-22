"""V2.0 经销商工作台 + 月度对账（M3.4/M3.5 数据聚合，无新表）

dashboard：余额/冻结/累计充值/累计消耗/已激活数/累计返点 概览；
statement：月度对账单（当月激活明细 + 返点记录）。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import (
    Agent,
    User,
    V2ActivationCode,
    V2DealerBalance,
    V2RebateRecord,
)
from ...schemas.v2.commerce import V2DashboardOut

router = APIRouter(prefix="/api/v2/dealer", tags=["v2-dashboard"])


async def _get_my_agent(session: AsyncSession, user_id: int):
    return (
        await session.execute(
            select(Agent).where(Agent.user_id == user_id, Agent.source == "v2")
        )
    ).scalars().first()


@router.get("/dashboard", response_model=V2DashboardOut)
async def dealer_dashboard(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商工作台聚合（余额/激活/返点 概览）。"""
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    bal = (
        await session.execute(
            select(V2DealerBalance).where(V2DealerBalance.agent_id == agent.id)
        )
    ).scalars().first()
    if not bal:
        raise HTTPException(404, "余额账户不存在")

    activated_count = (
        await session.execute(
            select(func.count())
            .select_from(V2ActivationCode)
            .where(
                V2ActivationCode.agent_id == agent.id,
                V2ActivationCode.status == "activated",
            )
        )
    ).scalar_one()
    total_rebate = (
        await session.execute(
            select(func.coalesce(func.sum(V2RebateRecord.rebate_amount), 0)).where(
                V2RebateRecord.agent_id == agent.id,
                V2RebateRecord.status == "settled",
            )
        )
    ).scalar_one()

    return V2DashboardOut(
        balance=bal.balance,
        frozen=bal.frozen,
        total_recharged=bal.total_recharged,
        total_consumed=bal.total_consumed,
        activated_count=int(activated_count or 0),
        total_rebate=Decimal(total_rebate or 0),
    )


@router.get("/statement")
async def dealer_statement(
    period: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商月度对账单（当月激活明细 + 返点记录）。

    period 格式 "YYYY-MM"，默认当月。
    """
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    today = date.today()
    period = period or f"{today.year:04d}-{today.month:02d}"
    try:
        year_s, month_s = period.split("-")
        year, month = int(year_s), int(month_s)
    except (ValueError, AttributeError):
        raise HTTPException(400, "period 格式应为 YYYY-MM")

    codes = (
        await session.execute(
            select(V2ActivationCode).where(V2ActivationCode.agent_id == agent.id)
        )
    ).scalars().all()
    month_codes = [
        c
        for c in codes
        if c.activated_at
        and c.activated_at.year == year
        and c.activated_at.month == month
    ]
    total_sales = sum(
        (c.price for c in month_codes if c.status == "activated"), Decimal("0")
    )

    rebate = (
        await session.execute(
            select(V2RebateRecord).where(
                V2RebateRecord.agent_id == agent.id,
                V2RebateRecord.period == period,
            )
        )
    ).scalars().first()

    return {
        "period": period,
        "activations": [
            {
                "id": c.id,
                "code": c.code,
                "price": float(c.price),
                "status": c.status,
                "activated_at": c.activated_at.isoformat() if c.activated_at else None,
            }
            for c in month_codes
        ],
        "total_sales": float(total_sales),
        "rebate": (
            {
                "tier": rebate.tier,
                "rebate_pct": float(rebate.rebate_pct),
                "amount": float(rebate.rebate_amount),
                "status": rebate.status,
            }
            if rebate
            else None
        ),
    }
