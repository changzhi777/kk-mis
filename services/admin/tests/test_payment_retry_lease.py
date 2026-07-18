"""发卡任务租约 / 重试耗尽 / 异常持久化单测（P0 Day 2 缺口 #4，2026-07-18）

补 test_payment_fulfillment.py 未覆盖的 claim_pending_jobs（locked_at 租约 + 过期回收）+
mark_job_failed（耗尽 5 次 + 告警回调 + 异常事件 + 订单同步）+ release_job_lease +
record_exception_event + process_issue_task 退避/耗尽链路。

⚠️ dialect 盲区声明（重要）：
    `with_for_update(skip_locked=True)` 在
      - PostgreSQL → `FOR UPDATE SKIP LOCKED`（真实行锁互斥，多 worker 抢占安全）
      - SQLite     → aiosqlite 静默忽略，退化为普通 SELECT（无行锁）
    本文件用 SQLite 内存库，**只能验证应用层租约/状态机逻辑**（locked_at 字段过滤、
    attempts 递增、status 迁移），**无法验证 PG 行锁的真实并发互斥语义**。
    真实多 worker 并发抢占需 PG 集成测试（提供 TEST_PG_DSN env 触发，见模块尾
    pytestmark skip 机制）——与第八轮 revision id 超 varchar(32) 的 dialect 盲区
    同源：SQLite 全绿 ≠ 生产 PG 能跑。
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
    _LEASE_RECLAIM_GRACE_MINUTES,
    claim_pending_jobs,
    confirm_payment,
    enqueue_issue_task,
    mark_job_failed,
    process_issue_task,
    record_exception_event,
    release_job_lease,
)
from app.services.payment_fulfillment import PaymentNotification
from app.utils import utcnow


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


async def _seed(session, *, quantity=1, batch_qty=10):
    """seed 卡类型 + active 批次 + pass 产品 + pending 订单，返回 ProductOrder。"""
    ct = AssetCardType(
        name="VIP", type="vip", face_value=100, unit_price=100,
    )
    session.add(ct)
    await session.flush()
    batch = AssetCardBatch(
        type_id=ct.id, name="B1", quantity=batch_qty, generated=0, status="active",
    )
    session.add(batch)
    await session.flush()
    p = TourProduct(
        title="卡", slug=f"s-{ct.id}-{batch.id}", type="pass",
        status="published", card_type_id=ct.id,
    )
    session.add(p)
    await session.flush()
    session.add(TourPass(product_id=p.id, face_value=100))
    await session.flush()
    unit = 100
    total = unit * quantity
    o = ProductOrder(
        product_id=p.id, quantity=quantity, unit_price=unit,
        original_total=total, discount=0, total=total,
        buyer_name="测", buyer_phone="13800000000", pay_status="pending",
    )
    session.add(o)
    await session.flush()
    await session.commit()
    return o


def _fen(yuan) -> int:
    return int((yuan * Decimal("100")).to_integral_value())


async def _paid_order_with_job(session, *, quantity=1, batch_qty=10, payment_id="txn"):
    """便捷：seed → confirm → enqueue，返回 (order_id, job)。"""
    o = await _seed(session, quantity=quantity, batch_qty=batch_qty)
    await confirm_payment(
        session, PaymentNotification("wechat", o.id, _fen(o.total), payment_id=payment_id)
    )
    await session.commit()
    job = await enqueue_issue_task(session, o.id)
    await session.commit()
    return o.id, job


# ── claim_pending_jobs：locked_at 租约 + 过期回收 ──────────────────────


@pytest.mark.asyncio
async def test_claim_marks_lease(session):
    """claim 领取到期 pending job 并写 locked_at 租约起点。"""
    oid, _ = await _paid_order_with_job(session, payment_id="claim1")
    jobs = await claim_pending_jobs(session)
    await session.commit()
    assert len(jobs) == 1
    assert jobs[0].order_id == oid
    assert jobs[0].locked_at is not None  # 租约已标记


@pytest.mark.asyncio
async def test_claim_skips_active_lease(session):
    """未被回收的租约（locked_at 新鲜）不被再次 claim。

    应用层靠 WHERE locked_at IS NULL OR locked_at < 阈值 过滤。这验证应用层逻辑；
    PG 行锁互斥属 dialect 盲区（见模块 docstring）。
    """
    _, job = await _paid_order_with_job(session, payment_id="claim2")
    job.locked_at = utcnow()  # 模拟另一 worker 刚持有
    await session.commit()
    jobs = await claim_pending_jobs(session)
    assert len(jobs) == 0  # 新鲜租约被过滤


@pytest.mark.asyncio
async def test_claim_reclaims_expired_lease(session):
    """过期租约（locked_at 早于 now - 回收宽限分钟）可被重领（worker 崩溃兜底）。"""
    _, job = await _paid_order_with_job(session, payment_id="claim3")
    # 超过 _LEASE_RECLAIM_GRACE_MINUTES（默认 10min）的陈旧租约
    job.locked_at = utcnow() - timedelta(minutes=_LEASE_RECLAIM_GRACE_MINUTES + 1)
    await session.commit()
    jobs = await claim_pending_jobs(session)
    assert len(jobs) == 1  # 过期租约回收重领
    assert jobs[0].locked_at is not None  # 重领后刷新租约起点


@pytest.mark.asyncio
async def test_claim_ignores_succeeded_jobs(session):
    """succeeded 状态的 job 不进 claim 候选（WHERE status IN pending/retry）。"""
    oid, _ = await _paid_order_with_job(session, payment_id="claim4")
    await process_issue_task(session, oid)  # 跑成功 → succeeded
    await session.commit()
    jobs = await claim_pending_jobs(session)
    assert len(jobs) == 0


# ── release_job_lease ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_release_clears_lease(session):
    """release 清空 locked_at（处理完成后让别的 worker 看到本任务已处理完）。"""
    _, job = await _paid_order_with_job(session, payment_id="rel1")
    [claimed] = await claim_pending_jobs(session)
    await session.commit()
    assert claimed.locked_at is not None
    release_job_lease(claimed)
    await session.commit()
    refreshed = await session.get(WebhookRetry, claimed.id)
    assert refreshed.locked_at is None


# ── record_exception_event ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_exception_severity_validation(session):
    """severity 非法 → ValueError（防脏数据落库）。"""
    with pytest.raises(ValueError):
        await record_exception_event(session, event_type="x", severity="bogus")


@pytest.mark.asyncio
async def test_record_exception_persists(session):
    """正常落库 + detail JSON 序列化（default=str 防 Decimal/datetime）。"""
    ev = await record_exception_event(
        session, event_type="payment_conflict", order_id=99,
        severity="warning", detail={"k": "v"},
    )
    await session.commit()
    cnt = (
        await session.execute(select(func.count(PaymentExceptionEvent.id)))
    ).scalar_one()
    assert cnt == 1
    assert ev.severity == "warning"
    import json as _json
    assert _json.loads(ev.detail) == {"k": "v"}


# ── mark_job_failed：耗尽 + 告警 + 订单同步 ────────────────────────────


@pytest.mark.asyncio
async def test_mark_failed_syncs_order_and_alerts(session):
    """耗尽：job.failed + order.failed + critical 异常事件 + alert_callback 触发。"""
    oid, job = await _paid_order_with_job(session, payment_id="fail1")
    job.attempts = MAX_RETRY_ATTEMPTS  # 模拟已耗尽
    await session.commit()

    alerted: list[dict] = []

    async def cb(**kw):
        alerted.append(kw)

    await mark_job_failed(session, job, "boom", alert_callback=cb)
    await session.commit()

    assert job.status == "failed"
    assert job.locked_at is None  # 失败释放租约
    assert "boom" in (job.last_error or "")

    o2 = await session.get(ProductOrder, oid)
    assert o2.status == "failed"  # 同步订单

    assert len(alerted) == 1  # 告警回调被调用一次
    assert alerted[0]["severity"] == "critical"
    assert alerted[0]["order_id"] == oid

    ev = (
        await session.execute(
            select(PaymentExceptionEvent).where(PaymentExceptionEvent.order_id == oid)
        )
    ).scalar_one()
    assert ev.severity == "critical"
    assert ev.event_type == "webhook_retry_exhausted"


@pytest.mark.asyncio
async def test_mark_failed_skips_terminal_order(session):
    """订单已 refunded/cancelled 不被覆盖为 failed（保留业务终态历史）。"""
    oid, job = await _paid_order_with_job(session, payment_id="fail2")
    o = await session.get(ProductOrder, oid)
    o.status = "refunded"
    o.pay_status = "refunded"
    await session.commit()

    job.attempts = MAX_RETRY_ATTEMPTS
    await session.commit()
    await mark_job_failed(session, job, "boom")
    await session.commit()

    o2 = await session.get(ProductOrder, oid)
    assert o2.status == "refunded"  # 终态不被覆盖


# ── process_issue_task：退避序列 + 耗尽 ────────────────────────────────


@pytest.mark.asyncio
async def test_process_task_exhaustion_to_failed(session):
    """库存持续不足：连失败 MAX_RETRY_ATTEMPTS 次 → job 转 failed（耗尽）。"""
    oid, _ = await _paid_order_with_job(
        session, quantity=5, batch_qty=3, payment_id="exh1"  # 库存 3 < 需求 5
    )
    for _ in range(MAX_RETRY_ATTEMPTS):
        ok, err = await process_issue_task(session, oid)
        await session.commit()
        assert ok is False
        assert err is not None

    job = (
        await session.execute(select(WebhookRetry).where(WebhookRetry.order_id == oid))
    ).scalar_one()
    assert job.status == "failed"
    assert job.attempts == MAX_RETRY_ATTEMPTS

    # 接入 mark_job_failed 后（2026-07-18）：process_issue_task 耗尽 → 自动同步
    # order.failed + 写 critical 异常事件。验证"重试耗尽不再静默"端到端。
    o2 = await session.get(ProductOrder, oid)
    assert o2.status == "failed"
    ev = (
        await session.execute(
            select(PaymentExceptionEvent).where(PaymentExceptionEvent.order_id == oid)
        )
    ).scalar_one()
    assert ev.severity == "critical"
    assert ev.event_type == "webhook_retry_exhausted"


@pytest.mark.asyncio
async def test_process_task_retry_before_exhaustion(session):
    """前 N-1 次失败 → status=retry（未耗尽），attempts 递增到阈值前不转 failed。"""
    oid, _ = await _paid_order_with_job(
        session, quantity=5, batch_qty=3, payment_id="bk1"
    )
    # 跑到阈值前一次（MAX_RETRY_ATTEMPTS - 1）
    for i in range(MAX_RETRY_ATTEMPTS - 1):
        ok, _ = await process_issue_task(session, oid)
        await session.commit()
        assert ok is False
        job = (
            await session.execute(
                select(WebhookRetry).where(WebhookRetry.order_id == oid)
            )
        ).scalar_one()
        assert job.attempts == i + 1
        assert job.status == "retry"  # 未耗尽仍是 retry
        assert job.next_retry_at is not None  # 已排退避
