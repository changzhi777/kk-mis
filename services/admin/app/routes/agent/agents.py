"""代理管理（区域代理，按 region_code 平级划分销售范围）

决策 #3 重构（2026-07-13）：从 3 级分销改为区域代理。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Agent, User
from ...schemas.agent import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(prefix="/api/v1/agent/agents", tags=["agent"])


@router.get("")
async def list_agents(
    region_code: str | None = Query(None, description="按区域过滤"),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:list")),
):
    """列出代理，可选 region_code 过滤"""
    stmt = select(Agent).order_by(Agent.region_code, Agent.id)
    if region_code:
        stmt = stmt.where(Agent.region_code == region_code)
    agents = (await session.execute(stmt)).scalars().all()
    return {"items": [AgentOut.model_validate(a).model_dump() for a in agents]}


@router.post("", response_model=AgentOut)
async def create_agent(
    req: AgentCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:save")),
):
    if not await session.get(User, req.user_id):
        raise HTTPException(400, "用户不存在")
    # 区域代码唯一性（同一区域只允许一个代理）
    existing = (
        await session.execute(
            select(Agent).where(
                Agent.region_code == req.region_code,
                Agent.status.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"区域 {req.region_code} 已有代理（{existing.name or existing.id}）")
    a = Agent(**req.model_dump())
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return AgentOut.model_validate(a)


@router.put("/{aid}", response_model=AgentOut)
async def update_agent(
    aid: int,
    req: AgentUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:save")),
):
    a = await session.get(Agent, aid)
    if not a:
        raise HTTPException(404, "代理不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await session.commit()
    await session.refresh(a)
    return AgentOut.model_validate(a)


@router.delete("/{aid}")
async def delete_agent(
    aid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:save")),
):
    a = await session.get(Agent, aid)
    if not a:
        raise HTTPException(404, "代理不存在")
    await session.delete(a)
    await session.commit()
    return {"success": True}
