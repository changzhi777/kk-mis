"""payment_fulfillment P0 Day 2.1 缺口 #4 修复测试（2026-07-15）

覆盖：
- claim_pending_jobs 租约（SELECT FOR UPDATE SKIP LOCKED + locked_at）
- release_job_lease 清空 locked_at
- mark_job_failed 同步订单 + 告警 + Prometheus
- record_exception_event 持久化异常事件
- MAX_ATTEMPTS=5 约定

用独立 SQLite 内存库（不走 conftest 的 client/init_db），直接测 service 层纯逻辑。
SQLite 对 SKIP LOCKED 退化（无 op 跳过同事务后续行），并发测试用单 session 内
invoke 多次 claim 验证 locked_at 标记确实写入。
"""
from datetime import timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import (
    AssetCardBatch,
    AssetCardType,
    Base,
    PaymentExceptionEvent,
    ProductOrder,
    TourPass,
    TourProduct,
    WebhookRetry,
)
from app.services.payment_fulfillment import (
    MAX_RETRY_ATTEMPTS,
    PaymentExceptionEvent as _PEE,  # noqa: F401 确保 import 可达
    claim_pending_jobs,
    mark_job_failed,
    record_exception_event,
    release_job_lease,
)
from app.utils import utcnow


# ── fixtures ───────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def session():
    """独立 SQLite 内存库 + create_all（隔离 conftest 全局 test.db）。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_order(session, *, status="paid"):
    """seed 一个最小可用的 paid 订单，返回 ProductOrder。"""
    ct = AssetCardType(
        name="VIP",
        type="vip",
        face_value=Decimal("100"),
        unit_price=Decimal("100"),
    )
    session.add(ct)
    await session.flush()
    p = TourProduct(
        title="卡",
        slug=f"s-{ct.id}",
        type="pass",
        status="published",
        card_type_id=ct.id,
    )
    session.add(p)
    await session.flush()
    session.add(TourPass(product_id=p.id, face_value=Decimal("100")))
    await session.flush()
    o = ProductOrder(
        product_id=p.id,
        quantity=1,
        unit_price=Decimal("100"),
        original_total=Decimal("100"),
        discount=0,
        total=Decimal("100"),
        buyer_name="测",
        buyer_phone="13800000000",
        pay_status="paid" if status in ("paid", "failed", "cancelled", "refunded") else "pending",
        status=status,
    )
    session.add(o)
    await session.flush()
    return o


async def _seed_retry(session, order_id: int, **kwargs):
    """seed 一个 WebhookRetry 任务，返回对象（不 commit）。"""
    defaults = {
        "order_id": order_id,
        "payload": {},
        "status": "pending",
        "next_retry_at": utcnow() - timedelta(seconds=1),  # 已到期
        "attempts": 0,
    }
    defaults.update(kwargs)
    job = WebhookRetry(**defaults)
    session.add(job)
    await session.flush()
    return job


# ── 1. claim_pending_jobs: 不重复领取 ────────────────────────────────


@pytest.mark.asyncio
async def test_claim_pending_jobs_no_double_claim_within_lease(session):
    """租约有效期内，第二次 claim 拿不到已 leased 的 job。

    SQLite 退化为整库锁，本测试用单 session 内两次 claim 验证：
    第一次 claim 后 locked_at 写入，第二次 claim 因 locked_at 未过 grace 期被过滤。
    """
    o = await _seed_order(session)
    job = await _seed_retry(session, o.id)
    await session.commit()

    # 第一次 claim → 拿到，locked_at 被设置
    claimed1 = await claim_pending_jobs(session, batch_size=10, lease_seconds=300)
    assert len(claimed1) == 1
    assert claimed1[0].id == job.id
    assert claimed1[0].locked_at is not None

    # 同一 session 内再次 claim → 同一 job 仍在租约窗口内，过滤掉
    claimed2 = await claim_pending_jobs(session, batch_size=10, lease_seconds=300)
    assert len(claimed2) == 0


# ── 2. 尊重租约 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_pending_jobs_respects_active_lease(session):
    """已被 lease 的 job 在 grace 期内不可重领。"""
    o = await _seed_order(session)
    job = await _seed_retry(session, o.id)
    await session.commit()

    claimed = await claim_pending_jobs(session, batch_size=10)
    assert len(claimed) == 1
    assert claimed[0].locked_at is not None

    # 在 grace 期（10min）内刷新 leased 时间也不应被重领
    job.locked_at = utcnow()  # 重新打点（5 分钟内）
    await session.flush()
    claimed2 = await claim_pending_jobs(session, batch_size=10)
    assert len(claimed2) == 0


# ── 3. 过期租约可重领 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_pending_jobs_releases_expired_lease(session):
    """locked_at 超过 grace 期（10 分钟）的任务可被新 claim 抢回。"""
    o = await _seed_order(session)
    job = await _seed_retry(session, o.id)
    # 模拟 15 分钟前的 lease
    job.locked_at = utcnow() - timedelta(minutes=15)
    job.status = "retry"  # 必须是 retry 状态（不是 succeeded）
    await session.flush()
    await session.commit()

    claimed = await claim_pending_jobs(session, batch_size=10)
    assert len(claimed) == 1
    assert claimed[0].id == job.id
    # 新 claim 重置 locked_at 为 now（应该非常接近）
    assert claimed[0].locked_at is not None
    delta = utcnow() - claimed[0].locked_at
    assert delta.total_seconds() < 5  # 5 秒内


# ── 4. release_job_lease 清空 locked_at ──────────────────────────────


@pytest.mark.asyncio
async def test_release_job_lease_clears_locked_at(session):
    """release_job_lease 应清空 locked_at 让别 worker 看到已处理完。"""
    o = await _seed_order(session)
    job = await _seed_retry(session, o.id)
    await session.flush()
    job.locked_at = utcnow()
    await session.flush()

    release_job_lease(job)
    await session.flush()

    assert job.locked_at is None


# ── 5. mark_job_failed 设 status ────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_job_failed_sets_status_to_failed(session):
    """mark_job_failed 后 job.status='failed' + last_error 写入（截断 500）。"""
    o = await _seed_order(session)
    job = await _seed_retry(session, o.id, attempts=MAX_RETRY_ATTEMPTS)
    await session.flush()

    long_err = "x" * 1000  # 1000 字符应截断到 500
    await mark_job_failed(session, job, long_err)
    await session.flush()

    assert job.status == "failed"
    assert len(job.last_error) == 500  # 已截断
    assert job.locked_at is None  # 释放租约


# ── 6. mark_job_failed 同步订单 status='failed' ─────────────────────


@pytest.mark.asyncio
async def test_mark_job_failed_synced_order_status(session):
    """未终态订单被 mark_failed 后 status='failed'。"""
    o = await _seed_order(session, status="paid")
    job = await _seed_retry(session, o.id, attempts=MAX_RETRY_ATTEMPTS)
    await session.flush()

    assert o.status == "paid"
    await mark_job_failed(session, job, "batch empty")
    await session.flush()

    o2 = await session.get(ProductOrder, o.id)
    assert o2.status == "failed"


# ── 7. mark_job_failed 不覆盖终态 ──────────────────────────────────


@pytest.mark.asyncio
async def test_mark_job_failed_does_not_override_terminal_status(session):
    """订单已是 refunded/cancelled 时 mark_failed 不覆盖（保留业务历史）。"""
    # refunded
    o_ref = await _seed_order(session, status="refunded")
    job_ref = await _seed_retry(session, o_ref.id, attempts=MAX_RETRY_ATTEMPTS)
    await session.flush()
    await mark_job_failed(session, job_ref, "err")
    await session.flush()
    assert o_ref.status == "refunded"  # 未覆盖

    # cancelled
    o_can = await _seed_order(session, status="cancelled")
    job_can = await _seed_retry(session, o_can.id, attempts=MAX_RETRY_ATTEMPTS)
    await session.flush()
    await mark_job_failed(session, job_can, "err")
    await session.flush()
    assert o_can.status == "cancelled"  # 未覆盖


# ── 8. mark_job_failed 触发告警回调 + Prometheus ────────────────────


@pytest.mark.asyncio
async def test_mark_job_failed_triggers_alert_callback(session):
    """alert_callback 应被调用 + Prometheus 计数自增（不抛错）。"""
    o = await _seed_order(session, status="paid")
    job = await _seed_retry(session, o.id, attempts=MAX_RETRY_ATTEMPTS)
    await session.flush()

    calls = []

    async def alert_cb(**kw):
        calls.append(kw)

    await mark_job_failed(session, job, "test error", alert_callback=alert_cb)
    await session.flush()

    assert len(calls) == 1
    call = calls[0]
    assert call["severity"] == "critical"
    assert call["event"] == "webhook_retry_exhausted"
    assert call["job_id"] == job.id
    assert call["order_id"] == o.id
    assert call["attempts"] == MAX_RETRY_ATTEMPTS
    assert call["last_error"] == "test error"


# ── 9. record_exception_event 持久化 ────────────────────────────────


@pytest.mark.asyncio
async def test_record_exception_event_persists(session):
    """record_exception_event 后查询能查到，detail 是 JSON 字符串。"""
    o = await _seed_order(session)
    await session.flush()

    detail = {"raw": {"amount": "100"}, "ts": "2026-07-15T18:00:00"}
    event = await record_exception_event(
        session,
        event_type="payment_conflict",
        order_id=o.id,
        payment_id="wx_txn_xxx",
        severity="warning",
        detail=detail,
    )
    await session.flush()

    # DB 中能查回
    cnt = (
        await session.execute(
            select(func.count(PaymentExceptionEvent.id)).where(
                PaymentExceptionEvent.event_type == "payment_conflict"
            )
        )
    ).scalar_one()
    assert cnt == 1

    # 字段校验
    fresh = await session.get(PaymentExceptionEvent, event.id)
    assert fresh.event_type == "payment_conflict"
    assert fresh.order_id == o.id
    assert fresh.payment_id == "wx_txn_xxx"
    assert fresh.severity == "warning"
    assert fresh.created_at is not None

    # 非法 severity 抛错
    with pytest.raises(ValueError):
        await record_exception_event(
            session,
            event_type="other",
            severity="nonsense",
            detail={},
        )
    await session.rollback()


# ── 10. MAX_ATTEMPTS 常量 ──────────────────────────────────────────


def test_max_attempts_constant_is_five():
    """MAX_RETRY_ATTEMPTS=5（与旧 docstring + 测试基线一致）。"""
    assert MAX_RETRY_ATTEMPTS == 5
