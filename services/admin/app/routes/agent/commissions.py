"""分润规则 + 记录 + 结算"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import CommissionRecord, CommissionRule
from ...schemas.agent import CommissionRecordOut, CommissionRuleCreate, CommissionRuleOut

router = APIRouter(prefix="/api/v1/agent/commissions", tags=["agent-commission"])


@router.get("/rules")
async def list_rules(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:view")),
):
    rules = (
        await session.execute(select(CommissionRule).order_by(CommissionRule.level))
    ).scalars().all()
    return {"items": [CommissionRuleOut.model_validate(r).model_dump() for r in rules]}


@router.post("/rules", response_model=CommissionRuleOut)
async def upsert_rule(
    req: CommissionRuleCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:save")),
):
    """upsert（level 唯一）"""
    existing = (
        await session.execute(select(CommissionRule).where(CommissionRule.level == req.level))
    ).scalar_one_or_none()
    if existing:
        existing.rate = req.rate
        existing.status = req.status
        await session.commit()
        await session.refresh(existing)
        return CommissionRuleOut.model_validate(existing)
    r = CommissionRule(**req.model_dump())
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return CommissionRuleOut.model_validate(r)


@router.get("/records")
async def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str = Query(None),
    agent_id: int = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:view")),
):
    stmt = select(CommissionRecord)
    if status:
        stmt = stmt.where(CommissionRecord.status == status)
    if agent_id:
        stmt = stmt.where(CommissionRecord.agent_id == agent_id)
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(stmt.order_by(CommissionRecord.id.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {
        "items": [CommissionRecordOut.model_validate(r).model_dump() for r in items],
        "total": total,
    }


@router.get("/summary")
async def summary(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:view")),
):
    """分润汇总：按 status 聚合金额"""
    rows = (
        await session.execute(
            select(CommissionRecord.status, func.sum(CommissionRecord.amount)).group_by(CommissionRecord.status)
        )
    ).all()
    return {"items": [{"status": r[0], "amount": float(r[1] or 0)} for r in rows]}


@router.post("/settle")
async def settle(
    agent_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:commission:save")),
):
    """结算某代理的 pending 分润 → settled"""
    records = (
        await session.execute(
            select(CommissionRecord).where(
                (CommissionRecord.agent_id == agent_id)
                & (CommissionRecord.status == "pending")
            )
        )
    ).scalars().all()
    for r in records:
        r.status = "settled"
        r.settled_at = datetime.utcnow()
    await session.commit()
    return {"success": True, "settled": len(records)}
