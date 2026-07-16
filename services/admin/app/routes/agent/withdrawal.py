"""A3 代理提现（WithdrawalRequest：申请→审核→打款）。

可提现余额 = settled referral commission（A2 推荐返佣已结算）。
门槛 ¥100。管理员审核 approve / paid / reject。

H7（2026-07-16）：审核状态机三态化，与 ReferralCommission 联动。
- approve：pending → approved；FIFO 选 agent 下 settled 返佣（累加到 >= amount）标 withdrawn，
  选中的 id 存到 WithdrawalRequest.remark（"commission_ids:[...]"）。
- paid：approved → paid；不动返佣（withdrawn 已在 approve 时落地，paid 仅记录打款事实）。
- reject：pending|approved → rejected；若已 approve，解析 remark 回滚 withdrawn → settled（钱退回可提现池）。
"""
import json
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, get_user_scope, require_permission
from ...models import Agent, ReferralCommission, User, WithdrawalRequest
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
    # 锁 Agent 行，串行化同 agent 的并发提现，防 TOCTOU 超额
    # （PG: SELECT ... FOR UPDATE；SQLite: SQLAlchemy 静默降级为普通 SELECT）
    locked_agent = (
        await session.execute(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        )
    ).scalars().first()
    if not locked_agent:
        raise HTTPException(403, "代理身份不存在")
    # 锁定后再算 settled/pending/available，保证校验与插入的原子性
    # H7：可提现 = settled referral - pending（未审核）提现
    # approved/paid 提现的返佣已在 approve 时标 withdrawn，已自动从 settled 扣除，
    # 不应再从 pending_amount 重复扣减，否则 available 被双算压缩。
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
                WithdrawalRequest.status == "pending",
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
    """代理可提现余额（H7：settled referral - pending 未审核提现）。"""
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
    # H7：只减 pending（未审核）提现，approved/paid 提现的返佣已 withdrawn 自动从 settled 扣除
    pending = (
        await session.execute(
            select(func.sum(WithdrawalRequest.amount)).where(
                WithdrawalRequest.agent_id == agent_id,
                WithdrawalRequest.status == "pending",
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
    # data_scope=self 数据隔离：仅返回自己代理的提现记录。
    # 注意：scope=="self" 但 my_agents 为空（用户无关联 Agent）时必须
    # 早返回空集，不能让 WHERE 被短路掉导致无过滤查询返回全部记录。
    # 与 routes/agent/orders.py:131 / commissions.py:65 同款写法。
    if scope == "self":
        if not my_agents:
            return {"items": []}
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
    action: str = Body(..., embed=True),  # approve / paid / reject
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("agent:commission:save")),
):
    """管理员审核提现（H7 状态机：approve → approved / paid → paid / reject → rejected）。

    与 ReferralCommission 联动：
    - approve：FIFO 选 agent 下 settled 返佣标 withdrawn（锁定，防重复提现）；
    - paid：仅记录打款事实（返佣已在 approve 时 withdrawn）；
    - reject：若已 approve，reclaim 对应 withdrawn → settled（钱退回可提现池）。
    """
    if action not in ("approve", "paid", "reject"):
        raise HTTPException(400, "action 必须为 approve / paid / reject")
    w = await session.get(WithdrawalRequest, wid)
    if not w:
        raise HTTPException(404, "提现记录不存在")

    if action == "approve":
        if w.status != "pending":
            raise HTTPException(400, f"状态 {w.status} 不可审核通过")
        # FIFO 选 settled 返佣，累加到 >= w.amount，标 withdrawn
        remaining = w.amount
        selected_ids: list[int] = []
        commissions = (
            await session.execute(
                select(ReferralCommission)
                .where(
                    ReferralCommission.agent_id == w.agent_id,
                    ReferralCommission.status == "settled",
                )
                .order_by(ReferralCommission.id.asc())
            )
        ).scalars().all()
        for c in commissions:
            if remaining <= 0:
                break
            c.status = "withdrawn"
            selected_ids.append(c.id)
            remaining -= c.amount
        if remaining > 0:
            # 理论不应发生（request_withdrawal 已校验 settled - pending >= amount），
            # 并发或数据异常时防御性拒绝，避免返佣被超额 withdrawn。
            raise HTTPException(400, f"settled 返佣不足覆盖提现金额（缺 {float(remaining)}）")
        w.status = "approved"
        w.reviewed_by = user.id
        w.reviewed_at = utcnow()
        w.remark = f"commission_ids:{json.dumps(selected_ids)}"
    elif action == "paid":
        if w.status != "approved":
            raise HTTPException(400, f"状态 {w.status} 不可标记打款（需先 approved）")
        # 仅记录打款事实；返佣 withdrawn 状态在 approve 时已落地，不重复修改
        w.status = "paid"
    else:  # reject
        if w.status not in ("pending", "approved"):
            raise HTTPException(400, f"状态 {w.status} 不可拒绝")
        # 若已 approve，reclaim 对应返佣 settled（钱退回可提现池）
        if w.status == "approved" and w.remark and w.remark.startswith("commission_ids:"):
            try:
                ids_payload = w.remark[len("commission_ids:"):]
                ids = [int(x) for x in json.loads(ids_payload)]
            except (ValueError, json.JSONDecodeError):
                ids = []
            if ids:
                to_reclaim = (
                    await session.execute(
                        select(ReferralCommission).where(
                            ReferralCommission.id.in_(ids),
                            ReferralCommission.status == "withdrawn",
                        )
                    )
                ).scalars().all()
                for c in to_reclaim:
                    c.status = "settled"
        w.status = "rejected"
        w.reviewed_by = user.id
        w.reviewed_at = utcnow()
        # 保留原 remark 用于审计追溯，追加 rejected 标记
        w.remark = (w.remark or "") + " | rejected"

    await session.commit()
    return {"id": w.id, "status": w.status}
