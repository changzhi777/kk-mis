"""CMS 支付履约领域服务（P0 Day 2，2026-07-15）

把"支付确认"和"发卡履约"从 routes/cms/orders.py 抽离为独立领域服务，
统一 mock 与真支付（wechat）两条链路：

    webhook/mock → confirm_payment(幂等支付事实) → issue_order_cards(多卡履约)

设计原则（详见 docs/cms-payments-webhook-p0.md）：
- 支付事实边界：金额校验/幂等记录/订单 paid 必须同事务持久化；
- 届约边界：多卡发放独立、可重入、可重试，失败只回滚本次发卡，
  不篡改已 paid 的支付事实（paid 不可逆回 pending）；
- 幂等：重复通知/重跑发卡均安全（PaymentIdempotency + OrderCard 唯一约束）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import string
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    AssetCard,
    AssetCardBatch,
    AssetCardType,
    Coupon,
    OrderCard,
    PaymentIdempotency,
    ProductOrder,
    ReferralCommission,
    TourProduct,
    WebhookRetry,
)
from ..security import hash_password
from ..utils import utcnow

logger = logging.getLogger(__name__)

# 发卡任务持久化重试配置（D4：BackgroundTasks 低延迟 + poller 兜底）
MAX_RETRY_ATTEMPTS = 5
_RETRY_BACKOFF_SECONDS = (30, 120, 600, 1800)  # 30s / 2m / 10m / 30m

# 幂等记录结果状态
IDEMPOTENCY_SUCCEEDED = "succeeded"
IDEMPOTENCY_PROCESSING = "processing"
IDEMPOTENCY_FAILED = "failed"

# 兼容旧 _issue_card 的防伪核销基址
_VERIFY_BASE_URL = "https://aisport.tech/oa/verify"


@dataclass
class PaymentNotification:
    """统一的支付通知（mock 与 wechat webhook 解析后都构造此结构）。

    amount_fen 用整数"分"，避免 float 金额校验误差（P0 方案硬要求）。
    """

    provider: str  # mock|wechat|alipay
    order_id: int
    amount_fen: int  # 实付金额（分）= order.total × 100
    payment_id: str = ""  # 网关交易号；mock 可空
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class IssueResult:
    """issue_order_cards 返回：本次新发卡的明文（一次性给买家，不落库多卡密码）。"""

    issued: list[tuple[str, str]]  # [(card_no, password_plain), ...]
    fulfilled: bool  # 是否已发齐


class PaymentConflictError(Exception):
    """支付确认/履约冲突（订单不存在/金额不符/状态非法/库存不足）。"""


def _payload_hash(payload: dict[str, Any]) -> str:
    """对 webhook payload 算 SHA-256（mock 空 dict 也有确定性 hash）。"""
    body = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(body).hexdigest()


async def confirm_payment(session: AsyncSession, n: PaymentNotification) -> ProductOrder:
    """幂等确认一笔支付：订单 pending → paid（支付事实边界）。

    幂等：相同 (provider, payment_id) 已 succeeded 的通知直接返回当前订单，
    不重复发券/返佣。事务由调用方 commit；本函数在同一 session（同事务）内
    完成"幂等记录 + 锁订单 + 金额校验 + 状态迁移 + 券核销 + 返佣"。
    """
    # 1) 幂等检查：payment_id 非空时查是否已处理过
    if n.payment_id:
        existing = (
            await session.execute(
                select(PaymentIdempotency)
                .where(
                    PaymentIdempotency.payment_provider == n.provider,
                    PaymentIdempotency.payment_id == n.payment_id,
                )
            )
        ).scalar_one_or_none()
        if existing and existing.result_status == IDEMPOTENCY_SUCCEEDED:
            order = await session.get(ProductOrder, n.order_id)
            if not order:
                raise PaymentConflictError(f"幂等记录存在但订单 {n.order_id} 不存在")
            return order  # 重复通知：幂等返回，不重复副作用

    # 2) 锁订单（PG: FOR UPDATE；SQLite: 退化为整库锁）
    order = (
        await session.execute(
            select(ProductOrder).where(ProductOrder.id == n.order_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not order:
        raise PaymentConflictError(f"订单 {n.order_id} 不存在")

    # 3) 金额校验（整数分，杜绝 float 误差）
    expected_fen = int((order.total * Decimal("100")).to_integral_value())
    if n.amount_fen != expected_fen:
        raise PaymentConflictError(
            f"金额不符：通知 {n.amount_fen} 分 ≠ 订单 {expected_fen} 分"
        )

    # 4) 状态机：已支付幂等返回；仅 pending 可转 paid
    if order.is_paid:
        return order
    if order.effective_status != "pending":
        raise PaymentConflictError(
            f"订单 {n.order_id} 状态 {order.effective_status} 非 pending，不可确认支付"
        )

    # 5) 支付事实迁移（双写：新 status + LEGACY pay_status 兼容窗口至 2026-09）
    order.status = "paid"
    order.pay_status = "paid"  # LEGACY 双写：ProductOrderOut 仍输出 pay_status
    order.paid_at = utcnow()
    if n.payment_id:
        order.transaction_id = n.payment_id

    # 6) 副作用 A：券核销（is_paid 守卫保证仅一次；FOR UPDATE 防并发 lost update）
    if order.coupon_id:
        coupon = (
            await session.execute(
                select(Coupon).where(Coupon.id == order.coupon_id).with_for_update()
            )
        ).scalar_one_or_none()
        if coupon:
            coupon.used_count += 1

    # 7) 副作用 B：推荐返佣（total × 5%，pending 待结算）
    if order.referrer_agent_id:
        commission = (order.total * Decimal("0.05")).quantize(Decimal("0.01"))
        order.referral_commission = commission
        session.add(
            ReferralCommission(
                agent_id=order.referrer_agent_id,
                product_order_id=order.id,
                amount=commission,
                status="pending",
            )
        )

    # 8) 写幂等记录（payment_id 为空时 mock 模式，不触发部分唯一约束）
    ttl = settings.payment_idempotency_ttl_seconds or 604800
    session.add(
        PaymentIdempotency(
            payment_provider=n.provider,
            payment_id=n.payment_id or None,
            order_id=order.id,
            request_body_hash=_payload_hash(n.raw_payload),
            result_status=IDEMPOTENCY_SUCCEEDED,
            expires_at=utcnow() + timedelta(seconds=ttl),
        )
    )
    return order


async def _pick_batch_with_stock(
    session: AsyncSession, card_type_id: int, need: int
) -> AssetCardBatch:
    """挑选有库存的批次（行锁防并发超卖）。

    优先 active 批次；无 active 时 fallback draft（自动转 active，兼容测试/初始）。
    PG 用 FOR UPDATE SKIP LOCKED；SQLite 退化无 SKIP LOCKED。
    """
    batch = (
        await session.execute(
            select(AssetCardBatch)
            .where(
                AssetCardBatch.type_id == card_type_id,
                AssetCardBatch.status == "active",
            )
            .with_for_update(skip_locked=True)
            .order_by(AssetCardBatch.id.desc())
        )
    ).scalars().first()
    if not batch:
        batch = (
            await session.execute(
                select(AssetCardBatch)
                .where(
                    AssetCardBatch.type_id == card_type_id,
                    AssetCardBatch.status == "draft",
                )
                .with_for_update(skip_locked=True)
                .order_by(AssetCardBatch.id.desc())
            )
        ).scalars().first()
        if not batch:
            raise PaymentConflictError(f"card_type={card_type_id} 无可用批次")
        batch.status = "active"
    available = (batch.quantity or 0) - (batch.generated or 0)
    if available < need:
        raise PaymentConflictError(f"批次 {batch.id} 剩余 {available} < 需求 {need}")
    return batch


async def issue_order_cards(session: AsyncSession, order_id: int) -> IssueResult:
    """为订单补发缺失的卡（届约边界，可重入）。

    流程：锁订单 → 算缺号（quantity − 已发 OrderCard）→ 产品 card_type →
    锁批次 + 库存校验 → 生成 N 张 AssetCard + N 行 OrderCard → 批次 generated += N →
    状态迁移。失败只回滚本次发卡事务，不篡改 paid 支付事实。
    """
    # 1) 锁订单
    order = (
        await session.execute(
            select(ProductOrder).where(ProductOrder.id == order_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not order:
        raise PaymentConflictError(f"订单 {order_id} 不存在")
    # 状态守卫：未支付/已取消/已退款 不可发卡（fulfilled 走下方 need<=0 幂等返回）
    if order.effective_status in ("pending", "cancelled", "refunded"):
        raise PaymentConflictError(
            f"订单 {order_id} 状态 {order.effective_status} 不可发卡"
        )

    # 2) 算缺号（已发 OrderCard 数 vs quantity）
    already = (
        await session.execute(
            select(func.count(OrderCard.id)).where(OrderCard.order_id == order_id)
        )
    ).scalar_one()
    need = order.quantity - already
    if need <= 0:
        order.status = "fulfilled"  # 已发齐：幂等（重跑/恢复都安全）
        return IssueResult(issued=[], fulfilled=True)

    # need > 0：仅 paid/card_issuing/failed 可继续（fulfilled 缺卡属数据异常）
    if order.effective_status not in ("paid", "card_issuing", "failed"):
        raise PaymentConflictError(
            f"订单 {order_id} 状态 {order.effective_status} 缺卡 {need} 张但不可发卡"
        )

    # 3) 产品 → card_type；无 card_type 则保持 paid（人工处理）
    product = await session.get(TourProduct, order.product_id)
    if not product or not product.card_type_id:
        order.status = "paid"
        return IssueResult(issued=[], fulfilled=False)
    card_type_id = product.card_type_id
    card_type = await session.get(AssetCardType, card_type_id)

    # 4) 锁批次 + 库存校验
    order.status = "card_issuing"
    batch = await _pick_batch_with_stock(session, card_type_id, need)

    # 5) 生成 N 张卡 + N 行 OrderCard（MEDIUM：批量 add + 单次 flush，DB 往返 N→1）
    cards: list[AssetCard] = []
    issued: list[tuple[str, str]] = []
    for _ in range(need):
        card_no = "".join(secrets.choice(string.digits) for _ in range(16))
        password = "".join(secrets.choice(string.digits) for _ in range(6))
        unique_code = secrets.token_hex(32)
        card = AssetCard(
            batch_id=batch.id,
            type_id=card_type_id,
            card_no=card_no,
            unique_code=unique_code,
            blockchain_tx_hash=uuid.uuid4().hex,
            qr_url=f"{_VERIFY_BASE_URL}/{unique_code}",
            password_hash=hash_password(password),
            face_value=card_type.face_value if card_type else 0,
            unit_price=card_type.unit_price if card_type else 0,
            status="issued",
        )
        cards.append(card)
        session.add(card)
        issued.append((card_no, password))
    await session.flush()  # 单次 flush 拿全部 card.id（原每张 flush 一次）
    for card in cards:
        session.add(OrderCard(order_id=order.id, card_id=card.id))

    # 6) 批次库存扣减
    batch.generated = (batch.generated or 0) + need

    # 7) 兼容旧单值字段（第一张卡号/密码，旧前端读 issued_card_no）
    if issued and not order.issued_card_no:
        order.issued_card_no, order.issued_card_password = issued[0]

    # 8) 发齐 → fulfilled
    order.status = "fulfilled"
    return IssueResult(issued=issued, fulfilled=True)


# ── 发卡任务持久化重试（D4：BackgroundTasks 低延迟 + poller 兜底）────────


async def enqueue_issue_task(
    session: AsyncSession, order_id: int, payload: dict[str, Any] | None = None
) -> WebhookRetry:
    """为订单建/复用发卡任务（uq order_id 保证一单一任务，幂等）。"""
    existing = (
        await session.execute(
            select(WebhookRetry).where(WebhookRetry.order_id == order_id)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    job = WebhookRetry(
        order_id=order_id,
        payload=payload or {},
        status="pending",
        next_retry_at=utcnow(),
    )
    session.add(job)
    return job


async def process_issue_task(
    session: AsyncSession, order_id: int
) -> tuple[bool, str | None]:
    """跑一次发卡任务：savepoint 内 issue_order_cards，失败只回滚发卡不篡改 paid。

    成功 → job.succeeded；失败 → 按 attempts 转 retry（退避）或 failed（耗尽）。
    事务边界：begin_nested() SAVEPOINT 保证发卡失败的 order 改动（如 card_issuing）
    回滚，而 job 状态标记保留在外层事务（P0 §3.4 届约边界）。
    """
    job = (
        await session.execute(
            select(WebhookRetry)
            .where(WebhookRetry.order_id == order_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not job:
        return False, "无发卡任务"
    if job.status == "succeeded":
        return True, None
    try:
        async with session.begin_nested():  # SAVEPOINT：发卡失败只回滚本次
            await issue_order_cards(session, order_id)
        job.status = "succeeded"
        job.updated_at = utcnow()
        return True, None
    except PaymentConflictError as e:
        # savepoint 已回滚（order 回 paid），外层事务保留 job 标记
        job.attempts = (job.attempts or 0) + 1
        job.last_error = str(e)
        if job.attempts >= MAX_RETRY_ATTEMPTS:
            job.status = "failed"
        else:
            job.status = "retry"
            idx = min(job.attempts - 1, len(_RETRY_BACKOFF_SECONDS) - 1)
            job.next_retry_at = utcnow() + timedelta(seconds=_RETRY_BACKOFF_SECONDS[idx])
        job.updated_at = utcnow()
        return False, str(e)


async def run_issue_task_async(order_id: int) -> None:
    """BackgroundTasks 回调：独立 session 跑发卡任务（脱离请求生命周期）。"""
    from ..db import SessionLocal

    if SessionLocal is None:
        return
    async with SessionLocal() as s:
        try:
            await process_issue_task(s, order_id)
            await s.commit()
        except Exception:
            logger.exception("BackgroundTasks 发卡失败 order=%s", order_id)
            await s.rollback()


async def poll_due_issue_tasks(
    session: AsyncSession, limit: int = 20
) -> list[WebhookRetry]:
    """扫描到期未完成的发卡任务（PG: FOR UPDATE SKIP LOCKED 抢占）。"""
    now = utcnow()
    return list(
        (
            await session.execute(
                select(WebhookRetry)
                .where(
                    WebhookRetry.status.in_(("pending", "retry")),
                    WebhookRetry.next_retry_at <= now,
                )
                .with_for_update(skip_locked=True)
                .order_by(WebhookRetry.next_retry_at)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def start_retry_poller() -> None:
    """lifespan 后台 poller：每 POLL 秒扫描到期任务发卡。

    ⚠️ 生产多实例部署需配合 PG SKIP LOCKED 抢占（poll_due_issue_tasks 已用），
    避免重复发卡。poller 只兜底；低延迟靠 webhook 的 BackgroundTasks。
    """
    from ..db import SessionLocal

    interval = settings.payment_retry_poll_seconds or 30
    logger.info("发卡重试 poller 启动，间隔 %ss", interval)
    while True:
        await asyncio.sleep(interval)
        if SessionLocal is None:
            continue
        try:
            async with SessionLocal() as s:
                jobs = await poll_due_issue_tasks(s)
                for job in jobs:
                    await process_issue_task(s, job.order_id)
                await s.commit()
        except Exception:
            logger.exception("发卡重试 poller 异常")
