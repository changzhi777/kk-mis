"""代理订单 + 完成时触发 3 级分润计算"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Agent, AgentOrder, AssetCardBatch, CommissionRecord, CommissionRule
from ...schemas.agent import OrderCreate, OrderOut

router = APIRouter(prefix="/api/v1/agent/orders", tags=["agent-order"])


async def _calc_commission(order: AgentOrder, session: AsyncSession):
    """订单完成 → 计算直接代理 + 上级代理的分润（记账，不碰资金）"""
    agent = await session.get(Agent, order.agent_id)
    if not agent:
        return
    rules = {
        r.level: r.rate
        for r in (
            await session.execute(select(CommissionRule).where(CommissionRule.status.is_(True)))
        ).scalars().all()
    }

    async def _record(ag: Agent):
        rate = ag.commission_rate or rules.get(ag.level, Decimal("0"))
        if rate > 0:
            session.add(
                CommissionRecord(
                    order_id=order.id, agent_id=ag.id, level=ag.level,
                    amount=order.total * rate, status="pending",
                )
            )

    await _record(agent)
    # 上级（二级代理 → 一级 parent）
    if agent.parent_id:
        parent = await session.get(Agent, agent.parent_id)
        if parent:
            await _record(parent)


@router.get("")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:order:list")),
):
    stmt = select(AgentOrder).order_by(AgentOrder.id.desc())
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {
        "items": [OrderOut.model_validate(o).model_dump() for o in items],
        "total": total,
    }


@router.post("", response_model=OrderOut)
async def create_order(
    req: OrderCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:order:save")),
):
    if not await session.get(Agent, req.agent_id):
        raise HTTPException(400, "代理不存在")
    if not await session.get(AssetCardBatch, req.batch_id):
        raise HTTPException(400, "批次不存在")
    total = req.quantity * req.unit_price
    o = AgentOrder(
        agent_id=req.agent_id, batch_id=req.batch_id, quantity=req.quantity,
        unit_price=req.unit_price, total=total, status="pending", remark=req.remark,
    )
    session.add(o)
    await session.commit()
    await session.refresh(o)
    return OrderOut.model_validate(o)


@router.post("/{order_id}/pay")
async def pay_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:order:save")),
):
    o = await session.get(AgentOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    if o.status != "pending":
        raise HTTPException(400, f"状态 {o.status} 不可付款")
    o.status = "paid"
    await session.commit()
    return {"success": True}


@router.post("/{order_id}/complete")
async def complete_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:order:save")),
):
    o = await session.get(AgentOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    if o.status != "paid":
        raise HTTPException(400, "订单需先确认付款(paid)才能完成")
    o.status = "completed"
    await _calc_commission(o, session)
    await session.commit()
    return {"success": True, "message": "订单完成，分润已计算"}
