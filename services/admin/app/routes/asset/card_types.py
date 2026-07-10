"""卡券类型路由"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import AssetCardType
from ...schemas.asset import CardTypeCreate, CardTypeOut, CardTypeUpdate

router = APIRouter(prefix="/api/v1/asset/card-types", tags=["asset-card-type"])


@router.get("")
async def list_card_types(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:type:list")),
):
    items = (
        await session.execute(select(AssetCardType).order_by(AssetCardType.id.desc()))
    ).scalars().all()
    return {"items": [CardTypeOut.model_validate(t).model_dump() for t in items]}


@router.post("", response_model=CardTypeOut)
async def create_card_type(
    req: CardTypeCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:type:save")),
):
    t = AssetCardType(**req.model_dump())
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return CardTypeOut.model_validate(t)


@router.put("/{tid}", response_model=CardTypeOut)
async def update_card_type(
    tid: int,
    req: CardTypeUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:type:save")),
):
    t = await session.get(AssetCardType, tid)
    if not t:
        from fastapi import HTTPException
        raise HTTPException(404, "卡券类型不存在")
    for k, v in req.model_dump().items():
        setattr(t, k, v)
    await session.commit()
    await session.refresh(t)
    return CardTypeOut.model_validate(t)


@router.delete("/{tid}")
async def delete_card_type(
    tid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:type:save")),
):
    t = await session.get(AssetCardType, tid)
    if not t:
        from fastapi import HTTPException
        raise HTTPException(404, "卡券类型不存在")
    await session.delete(t)
    await session.commit()
    return {"success": True}
