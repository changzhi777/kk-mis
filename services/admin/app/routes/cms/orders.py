"""CMS 权益卡订单路由（公开下单 + mock 支付 + admin 列表）

- 下单时锁定单价（product.pass_config.face_value）+ 优惠券算价
- 支付 mock（pending→paid，核销券 used_count）；不发真实 asset 卡（运营后续发卡）
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Coupon, ProductOrder, TourPass, TourProduct
from ...schemas.cms import ProductOrderCreate, ProductOrderOut
from ...utils import utcnow

router = APIRouter(prefix="/api/v1/cms/orders", tags=["cms-order"])


def _calc_discount(coupon: Coupon, original: Decimal) -> Decimal:
    if coupon.discount_type == "percent":
        return (original * coupon.discount_value / Decimal("100")).quantize(Decimal("0.01"))
    return min(coupon.discount_value, original)


@router.post("")
async def create_order(req: ProductOrderCreate, session: AsyncSession = Depends(get_session)):
    """公开下单（算价含优惠券，创建 pending 订单）"""
    p = await session.get(TourProduct, req.product_id)
    if not p or p.status != "published" or p.type != "pass":
        raise HTTPException(400, "仅已发布的权益卡（pass）产品可下单")
    pass_config = (
        await session.execute(select(TourPass).where(TourPass.product_id == p.id))
    ).scalar_one_or_none()
    if not pass_config:
        raise HTTPException(400, "产品缺少权益卡配置")
    unit_price = Decimal(str(pass_config.face_value or 0))
    original = unit_price * req.quantity
    discount = Decimal("0")
    coupon = None
    if req.coupon_code:
        coupon = (
            await session.execute(select(Coupon).where(Coupon.code == req.coupon_code))
        ).scalar_one_or_none()
        if not coupon or not coupon.status:
            raise HTTPException(400, "优惠券无效")
        now = utcnow()
        if coupon.valid_until and now > coupon.valid_until:
            raise HTTPException(400, "优惠券已过期")
        if original < coupon.min_total:
            raise HTTPException(400, f"未满 {coupon.min_total} 元")
        if coupon.max_uses > 0 and coupon.used_count >= coupon.max_uses:
            raise HTTPException(400, "优惠券已用完")
        discount = _calc_discount(coupon, original)
    total = max(original - discount, Decimal("0")).quantize(Decimal("0.01"))
    order = ProductOrder(
        product_id=p.id,
        quantity=req.quantity,
        unit_price=unit_price,
        original_total=original,
        discount=discount,
        total=total,
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        buyer_name=req.buyer_name,
        buyer_phone=req.buyer_phone,
        remark=req.remark,
        pay_status="pending",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return ProductOrderOut.model_validate(order).model_dump()


@router.post("/{order_id}/pay")
async def pay_order(order_id: int, session: AsyncSession = Depends(get_session)):
    """mock 支付（pending→paid，核销券 used_count）"""
    o = await session.get(ProductOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    if o.pay_status != "pending":
        raise HTTPException(400, f"订单状态 {o.pay_status}，不可支付")
    o.pay_status = "paid"
    o.paid_at = utcnow()
    if o.coupon_id:
        c = await session.get(Coupon, o.coupon_id)
        if c:
            c.used_count += 1
    await session.commit()
    await session.refresh(o)
    return ProductOrderOut.model_validate(o).model_dump()


@router.get("")
async def list_orders(
    pay_status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:order:list")),
):
    q = select(ProductOrder).order_by(ProductOrder.id.desc())
    if pay_status:
        q = q.where(ProductOrder.pay_status == pay_status)
    items = (await session.execute(q)).scalars().all()
    return {"items": [ProductOrderOut.model_validate(o).model_dump() for o in items]}
