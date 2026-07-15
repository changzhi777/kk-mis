"""CMS 权益卡订单路由（公开下单 + mock 支付 + admin 列表）

- 下单时锁定单价（product.pass_config.face_value）+ 优惠券算价
- 支付 mock（pending→paid，核销券 used_count）；不发真实 asset 卡（运营后续发卡）
"""
import io
import os
import secrets
import string
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import AssetCard, AssetCardBatch, AssetCardType, Coupon, ProductOrder, TourPass, TourProduct
from ...schemas.cms import ProductOrderCreate, ProductOrderOut
from ...security import hash_password
from ...services.notifier import notify
from ...utils import to_csv, utcnow

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
    # A2 推广码 → 推荐代理
    referrer_agent_id = None
    if req.promo_code:
        from ...models import Agent
        agent = (
            await session.execute(
                select(Agent).where(Agent.promo_code == req.promo_code, Agent.status.is_(True))
            )
        ).scalar_one_or_none()
        if agent:
            referrer_agent_id = agent.id
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
        referrer_agent_id=referrer_agent_id,
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
    # A2 推荐返佣（total * 5%，pending 待结算）
    if o.referrer_agent_id:
        referral = (o.total * Decimal("0.05")).quantize(Decimal("0.01"))
        o.referral_commission = referral
        from ...models import ReferralCommission
        session.add(ReferralCommission(
            agent_id=o.referrer_agent_id, product_order_id=o.id,
            amount=referral, status="pending",
        ))
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
    # webhook 通知新订单（旁路，失败静默）
    await notify("新订单", {"id": o.id, "buyer": o.buyer_name, "phone": o.buyer_phone, "total": str(o.total)})
    return ProductOrderOut.model_validate(o).model_dump()


@router.get("/export")
async def export_orders(
    pay_status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:order:list")),
):
    """导出订单 CSV"""
    q = select(ProductOrder).order_by(ProductOrder.id.desc())
    if pay_status:
        q = q.where(ProductOrder.pay_status == pay_status)
    items = (await session.execute(q)).scalars().all()
    rows = [
        [
            o.id, o.buyer_name, o.buyer_phone, o.quantity,
            str(o.unit_price), str(o.original_total), str(o.discount), str(o.total),
            o.coupon_code or "", o.pay_status, o.issued_card_no or "",
            o.created_at.isoformat() if o.created_at else "",
        ]
        for o in items
    ]
    cols = [
        ("id", "订单ID"), ("buyer_name", "买家"), ("buyer_phone", "电话"), ("quantity", "数量"),
        ("unit_price", "单价"), ("original_total", "原价"), ("discount", "优惠"), ("total", "实付"),
        ("coupon_code", "券码"), ("pay_status", "状态"), ("issued_card_no", "发出的卡号"), ("created_at", "时间"),
    ]
    return StreamingResponse(
        io.BytesIO(to_csv(rows, cols)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cms_orders.csv"'},
    )


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
