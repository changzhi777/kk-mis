"""CMS 合作商户路由（权益卡 C 用）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Merchant
from ...schemas.cms import MerchantCreate, MerchantOut, MerchantUpdate

router = APIRouter(prefix="/api/v1/cms/merchants", tags=["cms-merchant"])


@router.get("")
async def list_merchants(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:merchant:list")),
):
    items = (
        await session.execute(select(Merchant).order_by(Merchant.sort, Merchant.id.desc()))
    ).scalars().all()
    return {"items": [MerchantOut.model_validate(m).model_dump() for m in items]}


@router.post("", response_model=MerchantOut)
async def create_merchant(
    req: MerchantCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:merchant:save")),
):
    m = Merchant(**req.model_dump())
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return MerchantOut.model_validate(m)


@router.put("/{merchant_id}", response_model=MerchantOut)
async def update_merchant(
    merchant_id: int,
    req: MerchantUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:merchant:save")),
):
    m = await session.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404, "商户不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await session.commit()
    await session.refresh(m)
    return MerchantOut.model_validate(m)


@router.delete("/{merchant_id}")
async def delete_merchant(
    merchant_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:merchant:save")),
):
    m = await session.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404, "商户不存在")
    await session.delete(m)
    await session.commit()
    return {"success": True}
