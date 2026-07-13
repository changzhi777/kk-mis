"""年度返佣路由（决策 #3 重构 2026-07-13）

- GET  /api/v1/agent/yearly-commission?year=2026  — 查询
- POST /api/v1/agent/yearly-commission/settle      — 触发结算（手动或 cron）

2026-07-13 data_scope=self 数据隔离：list 仅返回自己代理的年度返佣。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_user_scope, require_permission
from ...models import YearlyCommissionRule
from ...schemas.agent import YearlyCommissionRecordOut, YearlyCommissionRuleOut
from ...services.yearly_commission import (
    get_yearly_commissions,
    settle_yearly_commissions,
)

router = APIRouter(prefix="/api/v1/agent/yearly-commission", tags=["agent-yearly-commission"])


@router.get("/rules")
async def list_rules(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:view")),
):
    """查询年度返佣阶梯规则（决策 #3：T1/T2/T3 阶梯，单一数据源消除前后端漂移）"""
    result = await session.execute(
        select(YearlyCommissionRule).order_by(YearlyCommissionRule.sort)
    )
    rules = result.scalars().all()
    return {
        "count": len(rules),
        "items": [YearlyCommissionRuleOut.model_validate(r).model_dump() for r in rules],
    }


@router.get("")
async def list_yearly_commissions(
    year: int = Query(..., ge=2000, le=2100, description="自然年"),
    region_code: Optional[str] = Query(None, description="区域过滤"),
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:commission:view")),
):
    """查询年度返佣记录（data_scope=self 时仅返回自己代理的）"""
    records = await get_yearly_commissions(session, year, region_code=region_code)
    # data_scope=self 后过滤：仅保留自己代理的记录
    scope, my_agent_ids = await get_user_scope(user, session)
    if scope == "self":
        records = [r for r in records if r.agent_id in my_agent_ids]
    return {
        "count": len(records),
        "year": year,
        "items": [YearlyCommissionRecordOut.model_validate(r).model_dump() for r in records],
    }


@router.post("/settle")
async def settle(
    year: int = Query(..., ge=2000, le=2100),
    dry_run: bool = Query(False, description="True 时只计算不写入"),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:save")),
):
    """触发年度返佣结算（通常 1 月初 cron 调用；仅 all 角色可调）"""
    records = await settle_yearly_commissions(session, year, dry_run=dry_run)
    return {
        "year": year,
        "settled_count": len(records),
        "dry_run": dry_run,
        "items": [YearlyCommissionRecordOut.model_validate(r).model_dump() for r in records],
    }
