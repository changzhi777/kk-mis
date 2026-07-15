"""A3 代理提现（WithdrawalRequest：申请→审核→打款）。

可提现余额 = settled referral commission（A2 推荐返佣已结算）。
门槛 ¥100。管理员审核 approve/reject。
"""
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, get_user_scope, require_permission
from ...models import ReferralCommission, User, WithdrawalRequest
from ...utils import utcnow

router = APIRouter(prefix="/api/v1/agent/withdrawals", tags=["agent-withdrawal"])

MIN_WITHDRAW = 100


class WithdrawalCreate(BaseModel):
    amount: Decimal
    bank_info: str


@router.post("")
async def request_withdrawal(
    body: WithdrawalCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """代理申请提现（可提现 = settled referral commission；门槛 ¥100）。"""
    scope, my_agents = await get_user_scope(user, session)
    if not my_agents:
        raise HTTPException(403, "非代理身份")
    agent_id = my_agents[0]
    # 可提现 = settled referral - 已申请（pending/approved）提现
    settled = (
        await session.execute(
            select(func.sum(ReferralCommission.amount)).where(
                ReferralCommission.agent_id == agent_id,
                ReferralCommission.status == "settled",
            )
        )
    ).scalar() or Decimal("0")
    pending_amount = (
        await session.execute(
            select(func.sum(WithdrawalRequest.amount)).where(
                WithdrawalRequest.agent_id == agent_id,
                WithdrawalRequest.status.in_(["pending", "approved"]),
            )
        )
    ).scalar() or Decimal("0")
    available = settled - pending_amount
    if body.amount < MIN_WITHDRAW:
        raise HTTPException(400, f"最低提现 ¥{MIN_WITHDRAW}")
    if body.amount > available:
        raise HTTPException(400, f"可提现余额不足（可用 ¥{available}）")
    w = WithdrawalRequest(agent_id=agent_id, amount=body.amount, bank_info=body.bank_info)
    session.add(w)
    await session.commit()
    return {"id": w.id, "status": "pending", "amount": float(body.amount), "available_after": float(available - body.amount)}


@router.get("/balance")
async def withdrawal_balance(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """代理可提现余额（settled referral - pending 提现）。"""
    scope, my_agents = await get_user_scope(user, session)
    if not my_agents:
        raise HTTPException(403, "非代理身份")
    agent_id = my_agents[0]
    settled = (
        await session.execute(
            select(func.sum(ReferralCommission.amount)).where(
                ReferralCommission.agent_id == agent_id,
                ReferralCommission.status == "settled",
            )
        )
    ).scalar() or Decimal("0")
    pending = (
        await session.execute(
            select(func.sum(WithdrawalRequest.amount)).where(
                WithdrawalRequest.agent_id == agent_id,
                WithdrawalRequest.status.in_(["pending", "approved"]),
            )
        )
    ).scalar() or Decimal("0")
    return {"settled": float(settled), "pending": float(pending), "available": float(settled - pending)}


@router.get("")
async def list_withdrawals(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """代理查自己提现记录（admin 查全部）。"""
    scope, my_agents = await get_user_scope(user, session)
    stmt = select(WithdrawalRequest)
    if scope == "self" and my_agents:
        stmt = stmt.where(WithdrawalRequest.agent_id.in_(my_agents))
    items = (
        await session.execute(stmt.order_by(WithdrawalRequest.id.desc()))
    ).scalars().all()
    return {
        "items": [
            {
                "id": w.id,
                "amount": float(w.amount),
                "status": w.status,
                "bank_info": w.bank_info,
                "reviewed_at": w.reviewed_at.isoformat() if w.reviewed_at else None,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in items
        ]
    }


@router.put("/{wid}/review")
async def review_withdrawal(
    wid: int,
    action: str = Body(..., embed=True),  # approve / reject
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("agent:commission:save")),
):
    """管理员审核提现（approve → approved / reject → rejected）。"""
    w = await session.get(WithdrawalRequest, wid)
    if not w:
        raise HTTPException(404, "提现记录不存在")
    if w.status != "pending":
        raise HTTPException(400, f"状态 {w.status} 不可审核")
    w.status = "approved" if action == "approve" else "rejected"
    w.reviewed_by = user.id
    w.reviewed_at = utcnow()
    await session.commit()
    return {"id": w.id, "status": w.status}
