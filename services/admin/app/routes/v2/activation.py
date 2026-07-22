"""V2.0 客户授权码 + 激活流（M2.1/2.2）

两类码分离（详见 memory）：
- 推广码（Agent.promo_code，经销商→客户扫）= 归属锁定；
- 授权码（V2ActivationCode，客户→经销商扫）= 激活付费。

激活流：客户生成授权码(扫推广码锁定经销商+选套餐，10min 时效) →
经销商扫码发起激活(冻结余额 balance→frozen) → 客户二次确认(frozen→consumed，套餐生效)。
4 项安全：客户主动生成 + 时效 + 一次性 + 客户二次确认（防经销商强制激活）。
"""
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import (
    Agent,
    TourPass,
    TourProduct,
    User,
    V2ActivationCode,
    V2DealerBalance,
    V2Membership,
)
from ...services.notifier import notify
from ...schemas.v2.activation import V2ActivationCodeCreate, V2ActivationCodeOut
from ...utils import utcnow

router = APIRouter(prefix="/api/v2/activation", tags=["v2-activation"])

_CODE_TTL_MINUTES = 10  # 授权码时效


def _gen_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


async def _find_my_agent(session: AsyncSession, user_id: int) -> Agent | None:
    return (
        await session.execute(
            select(Agent).where(Agent.user_id == user_id, Agent.source == "v2")
        )
    ).scalars().first()


async def _lock_balance(session: AsyncSession, agent_id: int) -> V2DealerBalance:
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


@router.post("/code", response_model=V2ActivationCodeOut)
async def create_activation_code(
    req: V2ActivationCodeCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """客户生成授权码（扫经销商推广码锁定归属 + 选套餐，10min 时效）。

    归属在此时锁定（agent_id），经销商后续扫码激活不需再确认归属。
    仅 pass 权益卡套餐支持（订制游询价制暂不支持）。
    """
    # 推广码 → 经销商（归属锁定）
    agent = (
        await session.execute(
            select(Agent).where(Agent.promo_code == req.promo_code, Agent.status.is_(True))
        )
    ).scalars().first()
    if not agent:
        raise HTTPException(404, "推广码无效")

    product = await session.get(TourProduct, req.product_id)
    if not product or product.status != "published":
        raise HTTPException(404, "套餐不存在或未发布")
    if product.type != "pass":
        raise HTTPException(400, "订制游暂不支持授权码激活，请选权益卡套餐")

    # 价格：TourPass.face_value（M2.4 接合同服务费率时细化）
    tp = (
        await session.execute(select(TourPass).where(TourPass.product_id == product.id))
    ).scalars().first()
    if not tp or tp.face_value is None or tp.face_value <= 0:
        raise HTTPException(400, "套餐未配置面值，无法激活")
    price = tp.face_value

    # 生成唯一 6 位 code
    for _ in range(5):
        code = _gen_code()
        clash = (
            await session.execute(
                select(V2ActivationCode).where(V2ActivationCode.code == code)
            )
        ).scalar_one_or_none()
        if not clash:
            break
    else:
        raise HTTPException(500, "授权码生成失败，请重试")

    ac = V2ActivationCode(
        code=code,
        customer_user_id=user.id,
        agent_id=agent.id,
        product_id=product.id,
        price=price,
        status="pending",
        expires_at=utcnow() + timedelta(minutes=_CODE_TTL_MINUTES),
    )
    session.add(ac)
    await session.commit()
    await session.refresh(ac)
    return ac


@router.get("/code/{code}", response_model=V2ActivationCodeOut)
async def get_activation_code(
    code: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """查授权码详情（归属经销商或生成客户可查；过期自动标记 expired）。"""
    ac = (
        await session.execute(
            select(V2ActivationCode).where(V2ActivationCode.code == code)
        )
    ).scalars().first()
    if not ac:
        raise HTTPException(404, "授权码不存在")

    my_agent = await _find_my_agent(session, user.id)
    if not (ac.customer_user_id == user.id or (my_agent and ac.agent_id == my_agent.id)):
        raise HTTPException(403, "无权查看此授权码")

    if ac.status == "pending" and utcnow() > ac.expires_at:
        ac.status = "expired"
        await session.commit()
        await session.refresh(ac)
    return ac


@router.post("/code/{code}/initiate", response_model=V2ActivationCodeOut)
async def initiate_activation(
    code: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商发起激活（冻结余额：balance→frozen，pending→activating）。

    仅归属经销商可发起；余额不足拒（409）。
    """
    ac = (
        await session.execute(
            select(V2ActivationCode).where(V2ActivationCode.code == code)
        )
    ).scalars().first()
    if not ac:
        raise HTTPException(404, "授权码不存在")

    my_agent = await _find_my_agent(session, user.id)
    if not my_agent or ac.agent_id != my_agent.id:
        raise HTTPException(403, "仅归属经销商可发起激活")
    if ac.status != "pending":
        raise HTTPException(409, f"授权码状态 {ac.status}，不可发起激活")
    if utcnow() > ac.expires_at:
        ac.status = "expired"
        await session.commit()
        raise HTTPException(409, "授权码已过期")

    bal = await _lock_balance(session, my_agent.id)
    if bal.balance < ac.price:
        raise HTTPException(409, "余额不足，请先充值")

    bal.balance -= ac.price
    bal.frozen += ac.price
    ac.status = "activating"
    ac.initiated_at = utcnow()
    await session.commit()
    await session.refresh(ac)
    return ac


@router.post("/code/{code}/confirm", response_model=V2ActivationCodeOut)
async def confirm_activation(
    code: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """客户二次确认（frozen→consumed，activating→activated，套餐生效）。

    仅授权码生成者（客户本人）可确认；确认后经销商冻结余额转消耗。
    TODO M2.4：触发阶梯返点累计；TODO：发卡/权益生效（接 asset 卡或 membership）。
    """
    ac = (
        await session.execute(
            select(V2ActivationCode).where(V2ActivationCode.code == code)
        )
    ).scalars().first()
    if not ac:
        raise HTTPException(404, "授权码不存在")
    if ac.customer_user_id != user.id:
        raise HTTPException(403, "仅授权码生成者可确认")
    if ac.status != "activating":
        raise HTTPException(409, f"授权码状态 {ac.status}，不可确认")

    bal = await _lock_balance(session, ac.agent_id)
    bal.frozen -= ac.price
    bal.total_consumed += ac.price
    ac.status = "activated"
    ac.activated_at = utcnow()
    # M3.2：建客户权益（套餐生效，闭合 M2.2 confirm 仅扣款的 TODO）
    session.add(
        V2Membership(
            customer_user_id=user.id,
            activation_code_id=ac.id,
            product_id=ac.product_id,
            status="active",
            activated_at=ac.activated_at,
        )
    )
    await session.commit()
    await session.refresh(ac)
    # M3.6：激活成功通知（旁路 webhook，不阻塞业务）
    await notify(
        "v2.activation.confirmed",
        {
            "activation_code_id": ac.id,
            "agent_id": ac.agent_id,
            "customer_user_id": ac.customer_user_id,
            "price": float(ac.price),
        },
    )
    return ac


@router.post("/code/{code}/refund", response_model=V2ActivationCodeOut)
async def refund_activation(
    code: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商退款（激活后取消，F16）：退经销商余额 + membership/ac → refunded。

    仅归属经销商 + activation status activated + membership 未核销（active）可退；
    已核销（membership used）→ 409。退款后返点月结自动排除（M2.4 查 status=activated）。
    """
    ac = (
        await session.execute(
            select(V2ActivationCode).where(V2ActivationCode.code == code)
        )
    ).scalars().first()
    if not ac:
        raise HTTPException(404, "授权码不存在")
    my_agent = await _find_my_agent(session, user.id)
    if not my_agent or ac.agent_id != my_agent.id:
        raise HTTPException(403, "仅归属经销商可退款")
    if ac.status != "activated":
        raise HTTPException(409, f"授权码状态 {ac.status}，不可退款")

    m = (
        await session.execute(
            select(V2Membership).where(
                V2Membership.activation_code_id == ac.id,
                V2Membership.customer_user_id == ac.customer_user_id,
                V2Membership.status == "active",
            )
        )
    ).scalars().first()
    if not m:
        raise HTTPException(409, "权益已核销或已失效，不可退款")

    bal = await _lock_balance(session, ac.agent_id)
    bal.balance += ac.price  # 退款入经销商可用余额
    m.status = "refunded"
    ac.status = "refunded"
    await session.commit()
    await session.refresh(ac)
    # M3.6：退款通知
    await notify(
        "v2.refund",
        {
            "activation_code_id": ac.id,
            "agent_id": ac.agent_id,
            "price": float(ac.price),
        },
    )
    return ac
