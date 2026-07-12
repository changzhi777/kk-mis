"""卡券列表/发放/作废"""
from ...utils import utcnow
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import AssetCard
from ...schemas.asset import CardOut, IssueRequest

router = APIRouter(prefix="/api/v1/asset/cards", tags=["asset-card"])


@router.get("")
async def list_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str = Query(None),
    batch_id: int = Query(None),
    keyword: str = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:card:list")),
):
    stmt = select(AssetCard)
    if status:
        stmt = stmt.where(AssetCard.status == status)
    if batch_id:
        stmt = stmt.where(AssetCard.batch_id == batch_id)
    if keyword:
        stmt = stmt.where(AssetCard.card_no.contains(keyword))
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(
            stmt.order_by(AssetCard.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [CardOut.model_validate(c).model_dump() for c in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/{card_id}/issue")
async def issue_card(
    card_id: int,
    req: IssueRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:card:save")),
):
    c = await session.get(AssetCard, card_id)
    if not c:
        raise HTTPException(404, "卡券不存在")
    if c.status != "draft":
        raise HTTPException(400, f"当前状态 {c.status} 不可发放")
    c.holder_user_id = req.holder_user_id
    c.status = "issued"
    c.issued_at = utcnow()
    await session.commit()
    return {"success": True}


@router.post("/{card_id}/void")
async def void_card(
    card_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:card:save")),
):
    c = await session.get(AssetCard, card_id)
    if not c:
        raise HTTPException(404, "卡券不存在")
    if c.status == "used":
        raise HTTPException(400, "已核销不可作废")
    c.status = "void"
    await session.commit()
    return {"success": True}
