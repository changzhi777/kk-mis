"""代理管理（3级树，二级必须挂一级）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Agent, User
from ...schemas.agent import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(prefix="/api/v1/agent/agents", tags=["agent"])


@router.get("")
async def list_agents(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:list")),
):
    agents = (
        await session.execute(select(Agent).order_by(Agent.level, Agent.id))
    ).scalars().all()
    return {"items": [AgentOut.model_validate(a).model_dump() for a in agents]}


@router.post("", response_model=AgentOut)
async def create_agent(
    req: AgentCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("agent:save")),
):
    if not await session.get(User, req.user_id):
        raise HTTPException(400, "用户不存在")
    if req.level == 2:
        if not req.parent_id:
            raise HTTPException(400, "二级代理必须有上级（一级代理）")
        parent = await session.get(Agent, req.parent_id)
        if not parent or parent.level != 1:
            raise HTTPException(400, "上级必须是一级代理")
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
