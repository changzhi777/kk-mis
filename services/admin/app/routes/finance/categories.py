"""收支科目路由（flat + CRUD）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import FinanceCategory
from ...schemas.finance import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/api/v1/finance/categories", tags=["finance-category"])


@router.get("")
async def list_categories(
    type: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:category:save")),
):
    stmt = select(FinanceCategory).order_by(FinanceCategory.type, FinanceCategory.sort, FinanceCategory.id)
    if type:
        stmt = stmt.where(FinanceCategory.type == type)
    cats = (await session.execute(stmt)).scalars().all()
    return {"items": [CategoryOut.model_validate(c).model_dump() for c in cats]}


@router.post("", response_model=CategoryOut)
async def create_category(
    req: CategoryCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:category:save")),
):
    c = FinanceCategory(**req.model_dump())
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return CategoryOut.model_validate(c)


@router.put("/{cid}", response_model=CategoryOut)
async def update_category(
    cid: int,
    req: CategoryUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:category:save")),
):
    c = await session.get(FinanceCategory, cid)
    if not c:
        raise HTTPException(404, "科目不存在")
    for k, v in req.model_dump().items():
        setattr(c, k, v)
    await session.commit()
    await session.refresh(c)
    return CategoryOut.model_validate(c)


@router.delete("/{cid}")
async def delete_category(
    cid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:category:save")),
):
    c = await session.get(FinanceCategory, cid)
    if not c:
        raise HTTPException(404, "科目不存在")
    await session.delete(c)
    await session.commit()
    return {"success": True}
