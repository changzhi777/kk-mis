"""V2.0 经销商充值 + 余额（M2.3，mock 网关立即确认；M2.5 接微信/支付宝真支付）

经销商 C 端化付款：充值买名额/余额，激活客户时扣减，余额不足不能激活。
M2.3 mock 渠道立即确认到账；wechat/alipay 渠道创建 pending 记录，待 M2.5 支付回调确认。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import Agent, User, V2DealerBalance, V2DealerRecharge
from ...schemas.v2.commerce import V2BalanceOut, V2RechargeCreate, V2RechargeOut
from ...utils import utcnow

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
