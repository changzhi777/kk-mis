"""代理订单 + 完成时触发阶梯折扣 + 单次返佣计算

决策 #3 重构（2026-07-13）：
- 区域代理（按 region_code）进货卡券批次
- 单次购买数量阶梯折扣（pricing.compute_vip_discount）
- 单次返佣基于年度累计销售额阶梯（pricing.compute_yearly_tier）

2026-07-13 data_scope=self 数据隔离：代理商仅看/操作自己代理的订单。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_user_scope, require_permission
from ...models import (
    Agent,
    AgentOrder,
    AssetCardBatch,
    AssetCardType,
    CommissionRecord,
)
from ...schemas.agent import OrderCreate, OrderOut
from ...services.pricing import (
    DEFAULT_VIP_UNIT_PRICE,
    compute_vip_discount,
    compute_yearly_tier,
    load_active_yearly_rules,
)

router = APIRouter(prefix="/api/v1/agent/orders", tags=["agent-order"])


async def _calc_commission(
    order: AgentOrder,
    session: AsyncSession,
    agent: Agent,
) -> None:
    """订单完成 → 计算单次返佣（基于年度累计销售额阶梯）

    阶梯来源：yearly_commission_rule 表（seed 默认 3 档：T1<50万30%/T2<200万40%/T3 50%）

    2026-07-13 性能修复：created_at range scan（半开区间）走复合索引 (agent_id, created_at, status)，
    替代原 func.extract("year", ...) 全表扫。
    """
    if order.created_at is None:
        return
    from datetime import datetime as _dt

    year = order.created_at.year
    year_start = _dt(year, 1, 1)
    year_end = _dt(year + 1, 1, 1)

    # 该年已完成的订单销售额合计（排除当前订单避免重复）
    completed_total = (
        await session.execute(
            select(func.coalesce(func.sum(AgentOrder.total), 0)).where(
                AgentOrder.agent_id == agent.id,
                AgentOrder.created_at >= year_start,
                AgentOrder.created_at < year_end,
                AgentOrder.status == "completed",
                AgentOrder.id != order.id,
            )
        )
    ).scalar_one() or Decimal("0")
    cumulative_sales = completed_total + order.total

    # 用 service 层加载规则 + compute_yearly_tier 纯函数（同 settle_yearly_commissions 复用）
    rules = await load_active_yearly_rules(session)
    tier, pct = compute_yearly_tier(cumulative_sales, rules)
    if pct > 0:
        amount = (order.total * pct).quantize(Decimal("0.01"))
        session.add(
            CommissionRecord(
                order_id=order.id,
                agent_id=agent.id,
                level=None,  # 决策 #3 推翻后无层级
                amount=amount,
                status="pending",
            )
        )


@router.get("/quote")
async def quote_price(
    batch_id: int = Query(..., gt=0),
    quantity: int = Query(..., gt=0),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:order:list")),
):
    """实时折扣预览（不创建订单）"""
    batch = await session.get(AssetCardBatch, batch_id)
    if not batch:
        raise HTTPException(404, "批次不存在")
    type_ = await session.get(AssetCardType, batch.type_id) if batch.type_id else None
    # 三级 fallback：batch.unit_price → type.unit_price → DEFAULT_VIP_UNIT_PRICE
    unit_price = (
        batch.unit_price
        or (type_.unit_price if type_ else None)
        or DEFAULT_VIP_UNIT_PRICE
    )

    tier, unit_price_actual, discount_pct = compute_vip_discount(quantity, unit_price)
    total = (unit_price_actual * Decimal(quantity)).quantize(Decimal("0.01"))
    return {
        "quantity": quantity,
        "original_unit_price": float(unit_price),
        "unit_price": float(unit_price_actual),
        "discount_pct": float(discount_pct),
        "tier": tier,
        "total": float(total),
    }


@router.get("")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:order:list")),
):
    # data_scope=self 数据隔离：仅看自己代理的订单
    scope, agent_ids = await get_user_scope(user, session)
    stmt = select(AgentOrder).order_by(AgentOrder.id.desc())
    if scope == "self":
        if not agent_ids:
            return {"items": [], "total": 0}
        stmt = stmt.where(AgentOrder.agent_id.in_(agent_ids))
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [OrderOut.model_validate(o).model_dump() for o in items],
        "total": total,
    }


@router.post("", response_model=OrderOut)
async def create_order(
    req: OrderCreate,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:order:save")),
):
    """创建订单：自动按 quantity 计算阶梯折扣"""
    agent = await session.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(400, "代理不存在")
    if not agent.status:
        raise HTTPException(400, "代理已停用")
    # data_scope=self 校验：只能给自己下单
    scope, agent_ids = await get_user_scope(user, session)
    if scope == "self" and req.agent_id not in agent_ids:
        raise HTTPException(403, "无权为该代理下单")
    batch = await session.get(AssetCardBatch, req.batch_id)
    if not batch:
        raise HTTPException(400, "批次不存在")

    # VIP 折扣（按 quantity 阶梯）— 统一 fallback
    type_ = await session.get(AssetCardType, batch.type_id) if batch.type_id else None
    unit_price_orig = (
        batch.unit_price
        or (type_.unit_price if type_ else None)
        or DEFAULT_VIP_UNIT_PRICE
    )
    tier, unit_price_actual, discount_pct = compute_vip_discount(req.quantity, unit_price_orig)
    total = (unit_price_actual * Decimal(req.quantity)).quantize(Decimal("0.01"))

    o = AgentOrder(
        agent_id=req.agent_id,
        batch_id=req.batch_id,
        quantity=req.quantity,
        unit_price=unit_price_actual,
        original_unit_price=unit_price_orig,
        discount_tier=tier,
        total=total,
        status="pending",
        region_code=agent.region_code,  # 冗余存（便于按区域汇总）
        remark=req.remark,
    )
    session.add(o)
    await session.commit()
    await session.refresh(o)
    return OrderOut.model_validate(o)


async def _assert_order_owner(o: AgentOrder, user, session: AsyncSession) -> None:
    """data_scope=self 时校验订单归属（pay/complete 复用）"""
    scope, agent_ids = await get_user_scope(user, session)
    if scope == "self" and o.agent_id not in agent_ids:
        raise HTTPException(403, "无权操作此订单")


@router.post("/{order_id}/pay")
async def pay_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:order:save")),
):
    o = await session.get(AgentOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    await _assert_order_owner(o, user, session)  # data_scope 校验
    if o.status != "pending":
        raise HTTPException(400, f"状态 {o.status} 不可付款")
    o.status = "paid"
    await session.commit()
    return {"success": True}


@router.post("/{order_id}/complete")
async def complete_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("agent:order:save")),
):
    """订单完成 → 触发单次返佣计算（基于年度累计阶梯）"""
    o = await session.get(AgentOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    await _assert_order_owner(o, user, session)  # data_scope 校验
    if o.status != "paid":
        raise HTTPException(400, "订单需先确认付款(paid)才能完成")
    o.status = "completed"
    agent = await session.get(Agent, o.agent_id)
    if agent:
        await _calc_commission(o, session, agent)
    await session.commit()
    return {
        "success": True,
        "message": "订单完成，单次返佣已计算",
        "unit_price": float(o.unit_price),
        "discount_tier": o.discount_tier,
        "total": float(o.total),
    }
