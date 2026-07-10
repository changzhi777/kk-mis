"""账户管理路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import FinanceAccount, FinanceTransaction
from ...schemas.finance import AccountCreate, AccountOut, AccountUpdate

router = APIRouter(prefix="/api/v1/finance/accounts", tags=["finance-account"])


@router.get("")
async def list_accounts(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:account:save")),
):
    accounts = (
        await session.execute(select(FinanceAccount).order_by(FinanceAccount.sort, FinanceAccount.id))
    ).scalars().all()
    return {"items": [AccountOut.model_validate(a).model_dump() for a in accounts]}


@router.post("", response_model=AccountOut)
async def create_account(
    req: AccountCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:account:save")),
):
    a = FinanceAccount(**req.model_dump())
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return AccountOut.model_validate(a)


@router.put("/{aid}", response_model=AccountOut)
async def update_account(
    aid: int,
    req: AccountUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:account:save")),
):
    a = await session.get(FinanceAccount, aid)
    if not a:
        raise HTTPException(404, "账户不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await session.commit()
    await session.refresh(a)
    return AccountOut.model_validate(a)


@router.delete("/{aid}")
async def delete_account(
    aid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:account:save")),
):
    a = await session.get(FinanceAccount, aid)
    if not a:
        raise HTTPException(404, "账户不存在")
    tx_count = (
        await session.execute(
            select(FinanceTransaction.id).where(FinanceTransaction.account_id == aid).limit(1)
        )
    ).first()
    if tx_count:
        raise HTTPException(400, "账户存在流水，不可删除")
    await session.delete(a)
    await session.commit()
    return {"success": True}
