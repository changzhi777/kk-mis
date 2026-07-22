"""V2.0 经销商充值 + 余额（M2.3 mock + M2.5 微信真支付回调，复用 P0 wechat_pay）

经销商 C 端化付款：充值买名额/余额，激活客户时扣减，余额不足不能激活。
- M2.3 mock 渠道立即确认到账；
- M2.5 wechat 渠道：POST /recharge/{id}/pay 调 gateway.pay 拿 code_url → 微信回调
  POST /recharge/notify/wechat 复用 P0 parse_notify_safe 验签 → confirm_recharge（幂等+金额校验+balance）；
- 支付宝 gateway 待新做（同微信模式，M2.5 先微信闭环）。
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import Agent, User, V2DealerBalance, V2DealerRecharge
from ...schemas.v2.commerce import V2BalanceOut, V2RechargeCreate, V2RechargeOut
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
from ...utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/dealer", tags=["v2-recharge"])

_CHANNELS = {"mock", "wechat", "alipay", "transfer"}


async def _get_my_agent(session: AsyncSession, user_id: int) -> Agent | None:
    return (
        await session.execute(select(Agent).where(Agent.user_id == user_id))
    ).scalars().first()


async def _lock_balance(session: AsyncSession, agent_id: int) -> V2DealerBalance:
    """锁余额行（PG FOR UPDATE；SQLite 静默忽略），资金操作必须锁。"""
    bal = (
        await session.execute(
            select(V2DealerBalance)
            .where(V2DealerBalance.agent_id == agent_id)
            .with_for_update()
        )
    ).scalars().first()
    if not bal:
        raise HTTPException(500, "余额账户缺失")
    return bal


@router.get("/balance", response_model=V2BalanceOut)
async def get_my_balance(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商查预付余额（可用 / 冻结 / 累计充值 / 累计消耗）。"""
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    bal = await _lock_balance(session, agent.id)
    return bal


@router.post("/recharge", response_model=V2RechargeOut)
async def create_recharge(
    req: V2RechargeCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商充值。

    - mock 渠道：立即确认到账（balance += amount），M2.3 测试用；
    - wechat/alipay/transfer：创建 pending 记录，待 M2.5 支付回调确认（与 P0 webhook 复用）。
    """
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    if req.channel not in _CHANNELS:
        raise HTTPException(400, "不支持的充值渠道")

    recharge = V2DealerRecharge(
        agent_id=agent.id, amount=req.amount, channel=req.channel, status="pending"
    )
    session.add(recharge)
    await session.flush()

    if req.channel == "mock":
        bal = await _lock_balance(session, agent.id)
        bal.balance += req.amount
        bal.total_recharged += req.amount
        recharge.status = "paid"
        recharge.paid_at = utcnow()
        recharge.txn_id = f"mock_{recharge.id}"

    await session.commit()
    await session.refresh(recharge)
    return recharge


@router.get("/recharge", response_model=list[V2RechargeOut])
async def list_recharges(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商充值记录（倒序）。"""
    agent = await _get_my_agent(session, user.id)
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    rows = (
        await session.execute(
            select(V2DealerRecharge)
            .where(V2DealerRecharge.agent_id == agent.id)
            .order_by(V2DealerRecharge.id.desc())
        )
    ).scalars().all()
    return rows


# ===== M2.5 真支付充值回调（复用 P0 wechat_pay）=====


async def confirm_recharge(
    session: AsyncSession, recharge_id: int, amount_fen: int, txn_id: str | None = None
):
    """经销商充值确认（微信回调触发）：幂等 + 金额校验 + balance += amount。

    Returns: (recharge, already_paid)。
    """
    rech = await session.get(V2DealerRecharge, recharge_id)
    if not rech:
        raise HTTPException(404, "充值记录不存在")
    if rech.status == "paid":
        return rech, True  # 幂等
    if rech.status != "pending":
        raise HTTPException(409, f"充值状态 {rech.status}，不可确认")
    amount_yuan = (Decimal(amount_fen) / Decimal(100)).quantize(Decimal("0.01"))
    if amount_yuan != rech.amount:
        raise HTTPException(400, f"金额不符：回调 {amount_yuan} != 充值 {rech.amount}")
    bal = await _lock_balance(session, rech.agent_id)
    bal.balance += rech.amount
    bal.total_recharged += rech.amount
    rech.status = "paid"
    rech.paid_at = utcnow()
    if txn_id:
        rech.txn_id = txn_id
    await session.commit()
    await session.refresh(rech)
    return rech, False


@router.post("/recharge/{recharge_id}/pay")
async def pay_recharge(
    recharge_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """发起支付（wechat 渠道调 WechatPayV3Gateway.pay 拿 code_url；已 paid 幂等返回）。

    TODO 支付宝：AlipayGateway 待新做（同微信模式，M2.5 先微信闭环）。
    """
    rech = await session.get(V2DealerRecharge, recharge_id)
    if not rech:
        raise HTTPException(404, "充值记录不存在")
    agent = await _get_my_agent(session, user.id)
    if not agent or rech.agent_id != agent.id:
        raise HTTPException(403, "无权操作此充值")
    if rech.status == "paid":
        return {"recharge_id": rech.id, "pay_url": None, "status": "paid"}
    if rech.channel != "wechat":
        raise HTTPException(400, f"渠道 {rech.channel} 暂不支持发起支付（仅 wechat）")
    try:
        gw = WechatPayV3Gateway.from_settings()
    except (FileNotFoundError, ValueError) as e:
        logger.warning("wechat 网关未配置: %s", e)
        raise HTTPException(503, "支付网关未配置（待商户密钥）")
    result = await gw.pay(rech.id, rech.amount, f"经销商充值{rech.id}")
    if not result.success:
        raise HTTPException(400, f"下单失败：{result.message}")
    rech.txn_id = result.transaction_id
    await session.commit()
    return {"recharge_id": rech.id, "pay_url": result.message, "status": rech.status}


@router.post("/recharge/notify/wechat")
async def recharge_notify_wechat(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """微信充值回调（复用 P0 parse_notify_safe 验签 → confirm_recharge）。

    异常映射同 P0 payments.py（401 验签 / 409 重放 / 400 内容）；
    金额冲突或已 paid 仍 ACK 200 SUCCESS（防微信重试风暴，待人工/幂等）。
    """
    raw = await request.body()
    headers = dict(request.headers)
    try:
        gw = WechatPayV3Gateway.from_settings()
    except (FileNotFoundError, ValueError):
        raise HTTPException(503, "支付网关未配置")
    try:
        notify = gw.parse_notify_safe(headers, raw)
    except WechatNotifySignatureError:
        raise HTTPException(401, "signature invalid")
    except WechatNotifyReplayError:
        raise HTTPException(409, "replay")
    except (
        WechatNotifyInvalidJSONError,
        WechatNotifyMissingFieldError,
        WechatNotifyInvalidResourceError,
        WechatNotifyDecryptError,
    ):
        raise HTTPException(400, "parse_notify invalid")
    except WechatNotifyError as e:
        raise HTTPException(status_code=e.http_status, detail=str(e))

    try:
        recharge_id = int(notify.out_trade_no)
    except (TypeError, ValueError):
        raise HTTPException(400, "out_trade_no 非法")
    try:
        await confirm_recharge(
            session, recharge_id, notify.amount_total_fen, notify.transaction_id
        )
    except HTTPException as e:
        if e.status_code == 409:  # 已 paid 幂等 ACK
            return {"code": "SUCCESS", "message": "OK"}
        if e.status_code == 400:  # 金额冲突 ACK 防重试风暴（同 P0 策略）
            logger.warning("充值确认金额冲突 recharge=%s", recharge_id)
            await session.rollback()
            return {"code": "SUCCESS", "message": "OK"}
        raise
    return {"code": "SUCCESS", "message": "OK"}
