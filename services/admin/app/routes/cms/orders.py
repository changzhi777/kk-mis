"""CMS 权益卡订单路由（公开下单 + mock 支付 + admin 列表）

- 下单时锁定单价（product.pass_config.face_value）+ 优惠券算价
- 支付 mock（pending→paid，核销券 used_count）；不发真实 asset 卡（运营后续发卡）
"""
import os
import secrets
import string
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import AssetCard, AssetCardBatch, AssetCardType, Coupon, ProductOrder, TourPass, TourProduct
from ...schemas.cms import ProductOrderCreate, ProductOrderOut
from ...security import hash_password
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


async def _issue_card(session: AsyncSession, card_type_id: int) -> tuple[str, str] | None:
    """从 card_type 找 active batch，生成 1 张卡，返回 (card_no, password) 明文；无 batch 返回 None"""
    batch = (
        await session.execute(
            select(AssetCardBatch)
            .where(AssetCardBatch.type_id == card_type_id, AssetCardBatch.status.in_(["draft", "active"]))
            .order_by(AssetCardBatch.id.desc())
        )
    ).scalars().first()
    if not batch:
        return None
    type_ = await session.get(AssetCardType, card_type_id)
    card_no = "".join(secrets.choice(string.digits) for _ in range(16))
    password = "".join(secrets.choice(string.digits) for _ in range(6))
    unique_code = secrets.token_hex(32)
    base_url = os.getenv("ANTICOUNTERFEIT_BASE_URL", "https://aisport.tech/oa/verify")
    session.add(
        AssetCard(
            batch_id=batch.id,
            type_id=card_type_id,
            card_no=card_no,
            unique_code=unique_code,
            blockchain_tx_hash=uuid.uuid4().hex,
            qr_url=f"{base_url}/{unique_code}",
            password_hash=hash_password(password),
            face_value=type_.face_value if type_ else 0,
            unit_price=type_.unit_price if type_ else 0,
            status="issued",
        )
    )
    batch.generated = (batch.generated or 0) + 1
    if batch.status == "draft":
        batch.status = "active"
    return card_no, password


@router.post("/{order_id}/pay")
async def pay_order(order_id: int, session: AsyncSession = Depends(get_session)):
    """支付（gateway.pay → paid → 券核销 + 自动发卡）"""
    from ...services.payment import gateway

    o = await session.get(ProductOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    if o.pay_status != "pending":
        raise HTTPException(400, f"订单状态 {o.pay_status}，不可支付")
    # 支付网关（mock 直接成功；真支付时 gateway 换真实现 + 密钥）
    result = await gateway.pay(o.id, o.total, subject=f"订单{o.id}")
    if not result.success:
        raise HTTPException(400, f"支付失败: {result.message}")
    o.pay_status = "paid"
    o.paid_at = utcnow()
    o.transaction_id = result.transaction_id
    if o.coupon_id:
        c = await session.get(Coupon, o.coupon_id)
        if c:
            c.used_count += 1
    # 真发卡（产品关联 card_type 时）
    p = await session.get(TourProduct, o.product_id)
    if p and p.card_type_id:
        issued = await _issue_card(session, p.card_type_id)
        if issued:
            o.issued_card_no, o.issued_card_password = issued
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
