"""支付回调路由（网关异步通知，P0 Day 2 重写，2026-07-15）

- mock 链路走 pay_order 同步（confirm + issue），webhook 一般不触发；
- wechat 链路：验签 → 解密 → confirm_payment 幂等 → 入队发卡 →
  BackgroundTasks 触发 → ACK。

验签失败回 401；支付确认冲突（金额不符等）仍 ACK（防微信重试风暴），记录待人工。
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...services.payment_fulfillment import (
    PaymentConflictError,
    PaymentNotification,
    confirm_payment,
    enqueue_issue_task,
    run_issue_task_async,
)
from ...services.wechat_pay import WechatPayV3Gateway

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cms/payments", tags=["cms-payment"])


@router.post("/notify/{gateway_name}")
async def payment_notify(
    gateway_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """网关异步回调。仅 wechat 真支付用；mock 走 pay_order 同步。"""
    if gateway_name != "wechat":
        return {"code": "SUCCESS", "message": "ignored"}
    return await _wechat_notify(request, background_tasks, session)


async def _wechat_notify(
    request: Request, background_tasks: BackgroundTasks, session: AsyncSession
):
    raw = await request.body()
    headers = request.headers
    try:
        gw = WechatPayV3Gateway.from_settings()
    except (FileNotFoundError, ValueError) as e:
        logger.error("微信网关初始化失败: %s", e)
        raise HTTPException(503, "支付网关未配置")
    notify = gw.parse_notify(
        headers.get("Wechatpay-Timestamp", ""),
        headers.get("Wechatpay-Nonce", ""),
        raw,
        headers.get("Wechatpay-Signature", ""),
    )
    if notify is None:
        raise HTTPException(401, "验签失败或时间窗超出")
    try:
        order_id = int(notify.out_trade_no)
    except (TypeError, ValueError):
        raise HTTPException(400, "out_trade_no 非法")
    # 幂等支付确认（金额不符等冲突：仍 ACK 防重试风暴，人工排查）
    try:
        await confirm_payment(
            session,
            PaymentNotification(
                provider="wechat",
                order_id=order_id,
                amount_fen=notify.amount_total_fen,
                payment_id=notify.transaction_id,
                raw_payload=notify.resource,
            ),
        )
    except PaymentConflictError as e:
        # 冲突时订单仍 pending（confirm 被回滚）：ACK 防微信重试风暴，但不入队发卡。
        # 否则 issue 因状态守卫失败 → retry 5 次转 failed，webhook 已 ACK 微信不重试
        # → 资金已扣但订单无 paid 记录，悬空无人知（P0 CRITICAL 2 修复）。
        logger.warning(
            "wechat 支付确认冲突 order=%s: %s（订单未 paid，待人工排查）", order_id, e
        )
        await session.rollback()
        return {"code": "SUCCESS", "message": "OK"}
    # 入队发卡任务（一单一任务，幂等）+ BackgroundTasks 低延迟触发
    await enqueue_issue_task(session, order_id, notify.resource)
    await session.commit()
    background_tasks.add_task(run_issue_task_async, order_id)
    return {"code": "SUCCESS", "message": "OK"}
