"""CMS 优惠券路由（admin CRUD + 公开校验 code）

- POST /validate：公开校验（下单时用，无需登录），返回折扣金额
- CRUD：admin 管理（需权限）
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Coupon
from ...schemas.cms import (
    CouponCreate,
    CouponOut,
    CouponUpdate,
    CouponValidateRequest,
    CouponValidateResponse,
)
from ...utils import utcnow

router = APIRouter(prefix="/api/v1/cms/coupons", tags=["cms-coupon"])


@router.post("/validate", response_model=CouponValidateResponse)
async def validate_coupon(req: CouponValidateRequest, session: AsyncSession = Depends(get_session)):
    """公开校验优惠券（下单时实时算折扣，无需登录）"""
    c = (
        await session.execute(select(Coupon).where(Coupon.code == req.code))
    ).scalar_one_or_none()
    if not c or not c.status:
        return CouponValidateResponse(valid=False, reason="券不存在或已停用")
    now = utcnow()
    if c.valid_until and now > c.valid_until:
        return CouponValidateResponse(valid=False, reason="已过期")
    if c.valid_from and now < c.valid_from:
        return CouponValidateResponse(valid=False, reason="未到生效时间")
    if req.total < c.min_total:
        return CouponValidateResponse(valid=False, reason=f"未满 {c.min_total} 元")
    if c.max_uses > 0 and c.used_count >= c.max_uses:
        return CouponValidateResponse(valid=False, reason="已用完")
    discount = (
        (req.total * c.discount_value / Decimal("100")).quantize(Decimal("0.01"))
        if c.discount_type == "percent"
        else min(c.discount_value, req.total)
    )
    return CouponValidateResponse(valid=True, discount=discount)


@router.get("")
async def list_coupons(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:coupon:list")),
):
    items = (
        await session.execute(select(Coupon).order_by(Coupon.id.desc()))
    ).scalars().all()
    return {"items": [CouponOut.model_validate(c).model_dump() for c in items]}


@router.post("", response_model=CouponOut)
async def create_coupon(
    req: CouponCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:coupon:save")),
):
    exists = (
        await session.execute(select(Coupon).where(Coupon.code == req.code))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "code 已存在")
    c = Coupon(**req.model_dump())
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return CouponOut.model_validate(c)


@router.put("/{coupon_id}", response_model=CouponOut)
async def update_coupon(
    coupon_id: int,
    req: CouponUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:coupon:save")),
):
    c = await session.get(Coupon, coupon_id)
    if not c:
        raise HTTPException(404, "优惠券不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await session.commit()
    await session.refresh(c)
    return CouponOut.model_validate(c)


@router.delete("/{coupon_id}")
async def delete_coupon(
    coupon_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:coupon:save")),
):
    c = await session.get(Coupon, coupon_id)
    if not c:
        raise HTTPException(404, "优惠券不存在")
    await session.delete(c)
    await session.commit()
    return {"success": True}
