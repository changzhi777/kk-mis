"""A1 推广码公开查询（无需登录，客户扫码看代理信息）。

订单用 promo_code 关联代理 + 返佣属 A2 推荐待业务决策，本路由只做公开查询。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...models import Agent

router = APIRouter(prefix="/api/v1/agent/promo", tags=["agent-promo"])


@router.get("/{code}")
async def get_agent_by_promo(code: str, session: AsyncSession = Depends(get_session)):
    """公开查询：推广码 → 代理信息（name/region）。"""
    agent = (
        await session.execute(
            select(Agent).where(Agent.promo_code == code, Agent.status.is_(True))
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "推广码无效")
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "region_code": agent.region_code,
        "region_name": agent.region_name,
    }
