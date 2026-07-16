"""分润规则 + 记录 + 结算

2026-07-13 data_scope=self 数据隔离：records/summary 仅返回自己代理的数据。
"""
from ...utils import utcnow

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_user_scope, require_permission
from ...models import AgentOrder, CommissionRecord, CommissionRule
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
    user=Depends(require_permission("agent:commission:view")),
):
    # data_scope=self 数据隔离：仅返回自己代理的返佣记录
    scope, my_agent_ids = await get_user_scope(user, session)
    stmt = select(CommissionRecord)
    # MEDIUM：status 过滤对 self/all 都生效（原 self 分支忽略 status）
    if status:
        stmt = stmt.where(CommissionRecord.status == status)
    if scope == "self":
        if not my_agent_ids:
            return {"items": [], "total": 0}
        stmt = stmt.where(CommissionRecord.agent_id.in_(my_agent_ids))
    elif agent_id:
        # all：尊重用户传的 agent_id 过滤（self 强制限 my_agent_ids）
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
    user=Depends(require_permission("agent:commission:view")),
):
    """分润汇总：按 status 聚合金额（data_scope=self 时仅汇总自己）"""
    scope, my_agent_ids = await get_user_scope(user, session)
    stmt = select(CommissionRecord.status, func.sum(CommissionRecord.amount))
    if scope == "self":
        if not my_agent_ids:
            return {"items": []}
        stmt = stmt.where(CommissionRecord.agent_id.in_(my_agent_ids))
    rows = (
        await session.execute(stmt.group_by(CommissionRecord.status))
    ).all()
    return {"items": [{"status": r[0], "amount": float(r[1] or 0)} for r in rows]}


@router.get("/dashboard")
async def dashboard(
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:commission:view")),
):
    """A4 代理看板：订单统计 + 返佣统计 + 区域排名（data_scope=self 仅自己）"""
    scope, my_agent_ids = await get_user_scope(user, session)
    if scope == "self" and not my_agent_ids:
        return {"orders": [], "commissions": [], "regions": []}

    def _self_filter(stmt, col):
        return stmt.where(col.in_(my_agent_ids)) if scope == "self" else stmt

    # 订单统计（按 status 聚合 count + total）
    order_stmt = _self_filter(
        select(AgentOrder.status, func.count(), func.sum(AgentOrder.total)),
        AgentOrder.agent_id,
    )
    order_rows = (await session.execute(order_stmt.group_by(AgentOrder.status))).all()
    orders = [{"status": r[0], "count": r[1], "total": float(r[2] or 0)} for r in order_rows]

    # 返佣统计（按 status 聚合 amount）
    comm_stmt = _self_filter(
        select(CommissionRecord.status, func.sum(CommissionRecord.amount)),
        CommissionRecord.agent_id,
    )
    comm_rows = (await session.execute(comm_stmt.group_by(CommissionRecord.status))).all()
    commissions = [{"status": r[0], "amount": float(r[1] or 0)} for r in comm_rows]

    # 区域排名（按 region_code 聚合订单总额，top 10）
    region_stmt = _self_filter(
        select(AgentOrder.region_code, func.sum(AgentOrder.total)).where(AgentOrder.region_code.isnot(None)),
        AgentOrder.agent_id,
    )
    region_rows = (
        await session.execute(
            region_stmt.group_by(AgentOrder.region_code)
            .order_by(func.sum(AgentOrder.total).desc())
            .limit(10)
        )
    ).all()
    regions = [{"region": r[0], "total": float(r[1] or 0)} for r in region_rows]

    return {"orders": orders, "commissions": commissions, "regions": regions}


@router.post("/settle")
async def settle(
    agent_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:commission:save")),
):
    """结算某代理的 pending 分润 → settled（仅 all 角色可调，代理商无 commission:save 权限）"""
    # LOW：data_scope=self 时校验 agent_id 属于自己（防越权结算他人代理）
    scope, my_agent_ids = await get_user_scope(user, session)
    if scope == "self" and agent_id not in (my_agent_ids or []):
        raise HTTPException(403, "无权结算此代理")
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
        r.settled_at = utcnow()
    await session.commit()
    return {"success": True, "settled": len(records)}
