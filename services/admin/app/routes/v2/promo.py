"""V2.0 经销商推广码（复用 Agent.promo_code，M2.1）

推广码 = 归属锁定（客户扫推广码注册/生成授权码时锁定经销商 agent_id）。
approve 时不自动生成，经销商首次调本端点懒生成（唯一 8 位，去掉易混字符 I/L/O/0/1）。
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import Agent, User
from ...schemas.v2.commerce import V2PromoCodeOut

router = APIRouter(prefix="/api/v2/dealer", tags=["v2-promo"])

# 去掉易混字符 I/L/O/0/1，降低客户手输/口述出错率
_PROMO_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _gen_promo_code() -> str:
    return "".join(secrets.choice(_PROMO_ALPHABET) for _ in range(8))


@router.get("/promo-code", response_model=V2PromoCodeOut)
async def get_my_promo_code(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商查看/懒生成自己的推广码。

    approve 时未生成；首次调用时生成唯一 8 位（重试 5 次避碰撞）。
    客户扫此码 → 生成授权码时锁定归属本经销商。
    """
    agent = (
        await session.execute(
            select(Agent).where(Agent.user_id == user.id, Agent.source == "v2")
        )
    ).scalars().first()
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份")
    if not agent.promo_code:
        for _ in range(5):
            code = _gen_promo_code()
            clash = (
                await session.execute(select(Agent).where(Agent.promo_code == code))
            ).scalar_one_or_none()
            if not clash:
                agent.promo_code = code
                break
        else:
            raise HTTPException(500, "推广码生成失败，请重试")
        await session.commit()
        await session.refresh(agent)
    return {"promo_code": agent.promo_code, "agent_id": agent.id}
