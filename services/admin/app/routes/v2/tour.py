"""V2.0 团期 + 客户预约（M3.1：预约团期 b-简，房+车 2 维先）

超管发布团期（含房+车资源库存）→ 客户激活套餐后预约团期出行（选人数 + 房/车，
锁团期容量 + 资源库存，并发安全 with_for_update）。
资源 b-简：M3 先 hotel+car，导游/餐/门票 M4/M5 补。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, require_permission
from ...models import (
    User,
    V2Membership,
    V2Reservation,
    V2ResourceStock,
    V2TourGroup,
)
from ...schemas.v2.tour import (
    V2MembershipOut,
    V2ReservationCreate,
    V2ReservationOut,
    V2ResourceStockOut,
    V2TourGroupCreate,
    V2TourGroupOut,
)
from ...utils import utcnow

router = APIRouter(prefix="/api/v2", tags=["v2-tour"])


async def _lock_tour_group(session: AsyncSession, tg_id: int) -> V2TourGroup:
    tg = (
        await session.execute(
            select(V2TourGroup).where(V2TourGroup.id == tg_id).with_for_update()
        )
    ).scalars().first()
    if not tg:
        raise HTTPException(404, "团期不存在")
    return tg


async def _load_resources(session: AsyncSession, tg_id: int) -> list:
    rows = (
        await session.execute(
            select(V2ResourceStock).where(V2ResourceStock.tour_group_id == tg_id)
        )
    ).scalars().all()
    return [V2ResourceStockOut.model_validate(r) for r in rows]


async def _to_group_out(session: AsyncSession, tg: V2TourGroup) -> V2TourGroupOut:
    out = V2TourGroupOut.model_validate(tg)
    out.resources = await _load_resources(session, tg.id)
    return out


@router.post("/tour-groups", response_model=V2TourGroupOut)
async def create_tour_group(
    req: V2TourGroupCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:tour:manage")),
):
    """超管发布团期（含房+车资源库存）。"""
    tg = V2TourGroup(
        product_id=req.product_id,
        title=req.title,
        start_date=req.start_date,
        end_date=req.end_date,
        capacity=req.capacity,
        status="open",
    )
    session.add(tg)
    await session.flush()
    for rtype, qty in (("hotel", req.hotel_qty), ("car", req.car_qty)):
        if qty > 0:
            session.add(
                V2ResourceStock(
                    tour_group_id=tg.id,
                    resource_type=rtype,
                    total_qty=qty,
                    used_qty=0,
                )
            )
    await session.commit()
    await session.refresh(tg)
    return await _to_group_out(session, tg)


@router.get("/tour-groups", response_model=list[V2TourGroupOut])
async def list_tour_groups(
    product_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """团期列表（登录可查；按 product_id 过滤，排除 closed）。"""
    q = (
        select(V2TourGroup)
        .where(V2TourGroup.status != "closed")
        .order_by(V2TourGroup.start_date)
    )
    if product_id is not None:
        q = q.where(V2TourGroup.product_id == product_id)
    tgs = (await session.execute(q)).scalars().all()
    return [await _to_group_out(session, tg) for tg in tgs]


@router.post("/reservation", response_model=V2ReservationOut)
async def create_reservation(
    req: V2ReservationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """客户预约团期（锁团期容量 + 房/车资源，扣减；不足 409）。"""
    tg = await _lock_tour_group(session, req.tour_group_id)
    if tg.status != "open":
        raise HTTPException(409, f"团期状态 {tg.status}，不可预约")
    if tg.capacity - tg.booked < req.people_count:
        raise HTTPException(409, "人数容量不足")

    for rtype, qty in (("hotel", req.hotel_qty), ("car", req.car_qty)):
        if qty > 0:
            rs = (
                await session.execute(
                    select(V2ResourceStock)
                    .where(
                        V2ResourceStock.tour_group_id == tg.id,
                        V2ResourceStock.resource_type == rtype,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if not rs or rs.total_qty - rs.used_qty < qty:
                raise HTTPException(409, f"{rtype} 资源不足")
            rs.used_qty += qty

    tg.booked += req.people_count
    if tg.booked >= tg.capacity:
        tg.status = "full"
    res = V2Reservation(
        customer_user_id=user.id,
        tour_group_id=tg.id,
        activation_code_id=req.activation_code_id,
        people_count=req.people_count,
        hotel_qty=req.hotel_qty,
        car_qty=req.car_qty,
        status="confirmed",
    )
    session.add(res)
    await session.commit()
    await session.refresh(res)
    return res


@router.get("/reservation", response_model=list[V2ReservationOut])
async def list_my_reservations(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """客户查自己的预约（倒序）。"""
    rows = (
        await session.execute(
            select(V2Reservation)
            .where(V2Reservation.customer_user_id == user.id)
            .order_by(V2Reservation.id.desc())
        )
    ).scalars().all()
    return rows


@router.post("/reservation/{res_id}/redeem", response_model=V2ReservationOut)
async def redeem_reservation(
    res_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:tour:manage")),
):
    """出行核销（超管/运营）：reservation confirmed→used + 关联 membership active→used。

    TODO M3.5：经销商工作台扫客户预约码核销（归属校验）。
    """
    res = await session.get(V2Reservation, res_id)
    if not res:
        raise HTTPException(404, "预约不存在")
    if res.status != "confirmed":
        raise HTTPException(409, f"预约状态 {res.status}，不可核销")
    res.status = "used"
    # 核销关联 membership（授权码来源的权益）
    if res.activation_code_id:
        m = (
            await session.execute(
                select(V2Membership).where(
                    V2Membership.activation_code_id == res.activation_code_id,
                    V2Membership.customer_user_id == res.customer_user_id,
                    V2Membership.status == "active",
                )
            )
        ).scalars().first()
        if m:
            m.status = "used"
            m.used_at = utcnow()
            m.reservation_id = res.id
    await session.commit()
    await session.refresh(res)
    return res


@router.get("/membership", response_model=list[V2MembershipOut])
async def list_my_memberships(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """客户查自己的套餐权益（倒序）。"""
    rows = (
        await session.execute(
            select(V2Membership)
            .where(V2Membership.customer_user_id == user.id)
            .order_by(V2Membership.id.desc())
        )
    ).scalars().all()
    return rows
