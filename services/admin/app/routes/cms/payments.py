"""支付回调路由（网关异步通知，P0 Day 2 重写 + 缺口 #3 修复，2026-07-15）

- mock 链路走 pay_order 同步（confirm + issue），webhook 一般不触发；
- wechat 链路：Redis 重放检测 → 验签 → 解密 → confirm_payment 幂等 →
  入队发卡 → BackgroundTasks 触发 → ACK。

异常分类映射（P0 Day 2 缺口 #3）：
  - WechatNotifySignatureError  → 401  验签/时间窗
  - WechatNotifyReplayError     → 409  同 timestamp+nonce 重放
  - WechatNotifyInvalidJSON / MissingField / InvalidResource / Decrypt
                              → 400  回调内容不合法
  - 其它 WechatNotifyError      → 子类 http_status（兜底）

支付确认冲突（金额不符等）仍 ACK 200 + SUCCESS（防微信重试风暴），记录待人工。
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
from ...services.wechat_pay import (
    WechatNotifyDecryptError,
    WechatNotifyError,
    WechatNotifyInvalidJSONError,
    WechatNotifyInvalidResourceError,
    WechatNotifyMissingFieldError,
    WechatNotifyReplayError,
    WechatNotifySignatureError,
    WechatPayV3Gateway,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cms/payments", tags=["cms-payment"])


# ── Redis 重放检测（P0 Day 2 缺口 #3，2026-07-15）───────────────────
# 防御场景：攻击者截获真实回调（已解密交易内容）后重复 POST 触发发卡。
# 时间窗 check_timestamp() 默认 ±300s 内可重放；用 Redis NX EX 86400 记
# timestamp+nonce 单次有效。Redis 不可用 → fail-open（不阻塞业务，与
# cache 模块策略一致）。

REPLAY_TTL_SECONDS = 86400  # 1 天，超过则允许重放（防 Redis 误持久化）


async def _check_replay(headers: dict) -> None:
    """Redis NX 检测重放（同 timestamp+nonce 重复 POST）。

    Raises:
        WechatNotifyReplayError: 已见过此 timestamp+nonce（重放攻击）。
    """
    from ...cache import _client as redis_client

    ts = headers.get("Wechatpay-Timestamp") or headers.get("wechatpay-timestamp") or ""
    nonce = headers.get("Wechatpay-Nonce") or headers.get("wechatpay-nonce") or ""
    if not ts or not nonce:
        return  # 无字段让 verify_callback 走 401 路径
    if redis_client is None:
        return  # Redis 不可用 fail-open
    key = f"wxpay:replay:{ts}:{nonce}"
    try:
        # NX=True 仅在 key 不存在时设置；返回 None 表示 key 已存在（重放）
        ok = await redis_client.set(key, "1", nx=True, ex=REPLAY_TTL_SECONDS)
    except Exception as e:  # Redis 异常 → fail-open
        logger.warning("replay check Redis fail-open: %s", e)
        return
    if not ok:
        raise WechatNotifyReplayError(f"replay detected ts={ts} nonce={nonce}")


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
    headers = dict(request.headers)

    # 0) Redis 重放检测（先于验签，避免攻击者反复触发 RSA 验签消耗 CPU）
    try:
        await _check_replay(headers)
    except WechatNotifyReplayError as e:
        logger.warning("wechat notify replay: %s", e)
        raise HTTPException(status_code=409, detail="replay")

    # 1) 网关初始化
    try:
        gw = WechatPayV3Gateway.from_settings()
    except (FileNotFoundError, ValueError) as e:
        logger.error("微信网关初始化失败: %s", e)
        raise HTTPException(503, "支付网关未配置")

    # 2) 验签 + 解密（parse_notify_safe 按异常类型 raise，路由层分类映射）
    try:
        notify = gw.parse_notify_safe(headers, raw)
    except WechatNotifySignatureError as e:
        logger.warning("wechat signature failed: %s", e)
        raise HTTPException(status_code=401, detail="signature invalid")
    except WechatNotifyReplayError as e:
        logger.warning("wechat replay: %s", e)
        raise HTTPException(status_code=409, detail="replay")
    except (
        WechatNotifyInvalidJSONError,
        WechatNotifyMissingFieldError,
        WechatNotifyInvalidResourceError,
        WechatNotifyDecryptError,
    ) as e:
        logger.warning("wechat parse_notify failed: %s", e)
        raise HTTPException(status_code=400, detail=f"parse_notify: {e}")
    except WechatNotifyError as e:
        # 兜底：未来新增异常类型未在路由显式映射时按子类 http_status 返回
        logger.warning("wechat notify error: %s", e)
        raise HTTPException(status_code=e.http_status, detail=str(e))

    # 3) 订单号解析（out_trade_no 应为可转 int 的字符串）
    try:
        order_id = int(notify.out_trade_no)
    except (TypeError, ValueError):
        raise HTTPException(400, "out_trade_no 非法")

    # 4) 幂等支付确认（金额不符等冲突：仍 ACK 防重试风暴，人工排查）
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

    # 5) 入队发卡任务（一单一任务，幂等）+ BackgroundTasks 低延迟触发
    await enqueue_issue_task(session, order_id, notify.resource)
    await session.commit()
    background_tasks.add_task(run_issue_task_async, order_id)
    return {"code": "SUCCESS", "message": "OK"}