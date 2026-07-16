"""payment_fulfillment 领域服务单测（P0 Day 2，2026-07-15）

覆盖 confirm_payment（幂等/金额/状态机/券核销）+ issue_order_cards（多卡/重跑/库存）。
用独立 SQLite 内存库（不走 conftest 的 client/init_db），直接测 service 层纯逻辑。
"""
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import (
    AssetCardBatch,
    AssetCardType,
    Base,
    Coupon,
    OrderCard,
    PaymentIdempotency,
    ProductOrder,
    TourPass,
    TourProduct,
    WebhookRetry,
)
from app.services.payment_fulfillment import (
    PaymentConflictError,
    PaymentNotification,
    confirm_payment,
    enqueue_issue_task,
    issue_order_cards,
    process_issue_task,
)


@pytest_asyncio.fixture
async def session():
    """独立 SQLite 内存库 + create_all，隔离 conftest 的全局 test.db。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed(session, *, quantity=1, batch_qty=10, total=None, with_coupon=False):
    """seed 卡类型 + 批次 + pass 产品 + 订单，返回 ProductOrder。"""
    ct = AssetCardType(name="VIP", type="vip", face_value=Decimal("100"), unit_price=Decimal("100"))
    session.add(ct)
    await session.flush()
    batch = AssetCardBatch(type_id=ct.id, name="B1", quantity=batch_qty, generated=0, status="active")
    session.add(batch)
    await session.flush()
    p = TourProduct(
        title="卡", slug=f"s-{ct.id}-{batch.id}", type="pass",
        status="published", card_type_id=ct.id,
    )
    session.add(p)
    await session.flush()
    session.add(TourPass(product_id=p.id, face_value=Decimal("100")))
    await session.flush()
    unit = Decimal("100")
    orig = unit * quantity
    total = orig if total is None else total
    coupon = None
    if with_coupon:
        coupon = Coupon(
            code=f"C{ct.id}", name="c", discount_type="fixed",
            discount_value=Decimal("10"), status=True,
        )
        session.add(coupon)
        await session.flush()
    o = ProductOrder(
        product_id=p.id, quantity=quantity, unit_price=unit,
        original_total=orig, discount=orig - total, total=total,
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        buyer_name="测", buyer_phone="13800000000", pay_status="pending",
    )
    session.add(o)
    await session.flush()
    await session.commit()
    return o


def _fen(yuan: Decimal) -> int:
    return int((yuan * Decimal("100")).to_integral_value())


# ── confirm_payment ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_payment_marks_paid(session):
    o = await _seed(session)
    res = await confirm_payment(session, PaymentNotification("mock", o.id, _fen(o.total)))
    await session.commit()
    assert res.status == "paid"
    assert res.paid_at is not None
    cnt = (await session.execute(select(func.count(PaymentIdempotency.id)))).scalar_one()
    assert cnt == 1


@pytest.mark.asyncio
async def test_confirm_payment_idempotent_same_payment_id(session):
    o = await _seed(session)
    n = PaymentNotification("wechat", o.id, _fen(o.total), payment_id="txn_1")
    await confirm_payment(session, n)
    await session.commit()
    await confirm_payment(session, n)  # 重复通知
    await session.commit()
    cnt = (await session.execute(select(func.count(PaymentIdempotency.id)))).scalar_one()
    assert cnt == 1  # 幂等记录只 1 条
    o2 = await session.get(ProductOrder, o.id)
    assert o2.status == "paid"


@pytest.mark.asyncio
async def test_confirm_payment_amount_mismatch(session):
    o = await _seed(session)
    with pytest.raises(PaymentConflictError):
        await confirm_payment(session, PaymentNotification("mock", o.id, _fen(o.total) + 1))
    await session.rollback()


@pytest.mark.asyncio
async def test_confirm_payment_wrong_state(session):
    o = await _seed(session)
    o.status = "cancelled"
    await session.commit()
    with pytest.raises(PaymentConflictError):
        await confirm_payment(session, PaymentNotification("mock", o.id, _fen(o.total)))
    await session.rollback()


@pytest.mark.asyncio
async def test_confirm_payment_consumes_coupon_once(session):
    o = await _seed(session, with_coupon=True, total=Decimal("90"))
    await confirm_payment(session, PaymentNotification("mock", o.id, _fen(o.total)))
    await session.commit()
    c = await session.get(Coupon, o.coupon_id)
    assert c.used_count == 1
    # 已 paid，再确认不重复核销
    await confirm_payment(
        session, PaymentNotification("wechat", o.id, _fen(o.total), payment_id="t2")
    )
    await session.commit()
    c2 = await session.get(Coupon, o.coupon_id)
    assert c2.used_count == 1


# ── issue_order_cards ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_issue_cards_multi_quantity(session):
    o = await _seed(session, quantity=3, batch_qty=10)
    await confirm_payment(session, PaymentNotification("mock", o.id, _fen(o.total)))
    await session.commit()
    r = await issue_order_cards(session, o.id)
    await session.commit()
    assert len(r.issued) == 3
    assert r.fulfilled is True
    cards = (
        await session.execute(select(func.count(OrderCard.id)).where(OrderCard.order_id == o.id))
    ).scalar_one()
    assert cards == 3
    o2 = await session.get(ProductOrder, o.id)
    assert o2.status == "fulfilled"


@pytest.mark.asyncio
async def test_issue_cards_idempotent_rerun(session):
    o = await _seed(session, quantity=3, batch_qty=10)
    await confirm_payment(session, PaymentNotification("mock", o.id, _fen(o.total)))
    await session.commit()
    r1 = await issue_order_cards(session, o.id)
    await session.commit()
    r2 = await issue_order_cards(session, o.id)
    await session.commit()
    assert len(r1.issued) == 3
    assert len(r2.issued) == 0  # 重跑无新卡
    assert r2.fulfilled is True
    cards = (
        await session.execute(select(func.count(OrderCard.id)).where(OrderCard.order_id == o.id))
    ).scalar_one()
    assert cards == 3  # 仍 3 张


@pytest.mark.asyncio
async def test_issue_cards_insufficient_stock(session):
    o = await _seed(session, quantity=5, batch_qty=3)  # 库存 3 < 需求 5
    oid = o.id  # rollback 会 expire 对象，提前保存
    total_fen = _fen(o.total)
    await confirm_payment(session, PaymentNotification("mock", oid, total_fen))
    await session.commit()
    with pytest.raises(PaymentConflictError):
        await issue_order_cards(session, oid)
    await session.rollback()
    o2 = await session.get(ProductOrder, oid)
    assert o2.status == "paid"  # 支付事实不被履约失败篡改


@pytest.mark.asyncio
async def test_confirm_then_issue_e2e(session):
    o = await _seed(session, quantity=2, batch_qty=10)
    await confirm_payment(
        session, PaymentNotification("wechat", o.id, _fen(o.total), payment_id="e2e_txn")
    )
    await session.commit()
    r = await issue_order_cards(session, o.id)
    await session.commit()
    assert len(r.issued) == 2
    assert r.fulfilled is True
    o2 = await session.get(ProductOrder, o.id)
    assert o2.status == "fulfilled"
    assert o2.transaction_id == "e2e_txn"


# ── 发卡任务队列（D4：process_issue_task savepoint + enqueue 幂等）───────

@pytest.mark.asyncio
async def test_process_issue_task_success(session):
    o = await _seed(session, quantity=2, batch_qty=10)
    oid = o.id
    await confirm_payment(session, PaymentNotification("wechat", oid, _fen(o.total), payment_id="t1"))
    await session.commit()
    await enqueue_issue_task(session, oid)
    await session.commit()
    ok, err = await process_issue_task(session, oid)
    await session.commit()
    assert ok is True and err is None
    job = (
        await session.execute(select(WebhookRetry).where(WebhookRetry.order_id == oid))
    ).scalar_one()
    assert job.status == "succeeded"
    o2 = await session.get(ProductOrder, oid)
    assert o2.status == "fulfilled"


@pytest.mark.asyncio
async def test_process_issue_task_retry_on_stock_fail(session):
    """库存不足 → savepoint 回滚发卡（order 回 paid），job 转 retry（不篡改支付事实）。"""
    o = await _seed(session, quantity=5, batch_qty=3)
    oid = o.id
    await confirm_payment(session, PaymentNotification("wechat", oid, _fen(o.total), payment_id="t2"))
    await session.commit()
    await enqueue_issue_task(session, oid)
    await session.commit()
    ok, err = await process_issue_task(session, oid)
    await session.commit()
    assert ok is False
    assert err is not None
    job = (
        await session.execute(select(WebhookRetry).where(WebhookRetry.order_id == oid))
    ).scalar_one()
    assert job.status == "retry"
    assert job.attempts == 1
    o2 = await session.get(ProductOrder, oid)
    assert o2.status == "paid"  # savepoint 回滚：支付事实未被履约失败篡改


@pytest.mark.asyncio
async def test_enqueue_issue_task_idempotent(session):
    o = await _seed(session, quantity=1, batch_qty=10)
    oid = o.id
    j1 = await enqueue_issue_task(session, oid, {"x": 1})
    await session.commit()
    j2 = await enqueue_issue_task(session, oid, {"x": 2})
    await session.commit()
    assert j1.id == j2.id  # 同一任务（uq order_id 幂等）
