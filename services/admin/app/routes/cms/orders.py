"""CMS 权益卡订单路由（公开下单 + mock 支付 + admin 列表）

- 下单时锁定单价（product.pass_config.face_value）+ 优惠券算价
- 支付 mock（pending→paid，核销券 used_count）；不发真实 asset 卡（运营后续发卡）
"""
import io
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ... import cache
from ...db import get_session
from ...deps import require_permission
from ...models import Coupon, ProductOrder, TourPass, TourProduct
from ...schemas.cms import ProductOrderCreate, ProductOrderDetailOut, ProductOrderOut
from ...services.notifier import notify
from ...utils import to_csv, utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cms/orders", tags=["cms-order"])


def _calc_discount(coupon: Coupon, original: Decimal) -> Decimal:
    if coupon.discount_type == "percent":
        return (original * coupon.discount_value / Decimal("100")).quantize(Decimal("0.01"))
    return min(coupon.discount_value, original)


@router.post("")
async def create_order(
    req: ProductOrderCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """公开下单（算价含优惠券，创建 pending 订单）

    H17：公开端点 IP 限流 30/min（防"卡农场"批量刷单）。
    """
    # H17 限流（fail-open：Redis 不可用放行）
    ip = request.client.host if request.client else "unknown"
    if not await cache.rate_limit_check(f"ratelimit:cms_order:{ip}", 30, 60):
        raise HTTPException(429, "下单过于频繁，请稍后再试")
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


@router.post("/{order_id}/pay")
async def pay_order(order_id: int, session: AsyncSession = Depends(get_session)):
    """支付（gateway.pay → confirm_payment 幂等确认 → issue_order_cards 发卡履约）

    mock 与真支付（wechat）共用 payment_fulfillment 链路；真支付时 gateway 换真实现，
    webhook 异步回调也调同一 confirm_payment（幂等）。

    事务边界（P0 §3.4 届约分层）：
    - 行锁（FOR UPDATE）贯穿 pending 检查 → gateway.pay → confirm，防并发双扣；
    - 支付事实（confirm_payment → paid）先 commit 落库，不可逆；
    - 发卡履约（issue_order_cards）在独立 SAVEPOINT 内执行，失败只回滚发卡，
      订单保持 paid（响应标注"发卡待重试"），不回滚支付事实。
    """
    from ...config import settings
    from ...services.payment import gateway
    from ...services.payment_fulfillment import (
        PaymentConflictError,
        PaymentNotification,
        confirm_payment,
        issue_order_cards,
    )

    # CRITICAL 3 修复：行锁防并发双扣（PG: FOR UPDATE；SQLite: 整库锁）
    o = (
        await session.execute(
            select(ProductOrder).where(ProductOrder.id == order_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not o:
        raise HTTPException(404, "订单不存在")
    if o.effective_status != "pending":
        raise HTTPException(400, f"订单状态 {o.effective_status}，不可支付")
    # 支付网关（mock 直接成功；真支付 gateway 换 WechatPayV3Gateway）
    result = await gateway.pay(o.id, o.total, subject=f"订单{o.id}")
    if not result.success:
        raise HTTPException(400, f"支付失败: {result.message}")
    # 幂等支付确认（券核销 + 返佣 + 双写 status/pay_status，统一 mock/wechat 链路）
    amount_fen = int((o.total * Decimal("100")).to_integral_value())
    try:
        await confirm_payment(
            session,
            PaymentNotification(
                provider=settings.payment_provider,
                order_id=o.id,
                amount_fen=amount_fen,
                payment_id=result.transaction_id,
                raw_payload={"source": "sync_pay", "transaction_id": result.transaction_id},
            ),
        )
    except PaymentConflictError as e:
        await session.rollback()
        raise HTTPException(400, str(e))
    # CRITICAL 4 修复：支付事实先 commit（paid 不可逆）；发卡用 SAVEPOINT 隔离
    await session.commit()
    await session.refresh(o)

    # 发卡履约（SAVEPOINT：失败只回滚发卡，订单保持 paid）
    issue_pending = False
    try:
        async with session.begin_nested():
            await issue_order_cards(session, o.id)
        await session.commit()
    except PaymentConflictError as e:
        logger.warning("订单 %s 发卡失败（保持 paid，发卡待重试）: %s", order_id, e)
        await session.rollback()
        issue_pending = True
    await session.refresh(o)
    # webhook 通知新订单（旁路，失败静默）
    await notify("新订单", {"id": o.id, "buyer": o.buyer_name, "phone": o.buyer_phone, "total": str(o.total)})
    out = ProductOrderDetailOut.model_validate(o).model_dump()
    if issue_pending:
        out["issue_pending"] = True
    return out


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
