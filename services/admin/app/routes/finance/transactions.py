"""收支流水路由（录入/删除时联动账户余额）"""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import FinanceAccount, FinanceCategory, FinanceTransaction, User
from ...schemas.finance import TransactionCreate, TransactionOut

router = APIRouter(prefix="/api/v1/finance/transactions", tags=["finance-transaction"])


@router.post("", response_model=TransactionOut)
async def create_transaction(
    req: TransactionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("finance:transaction:save")),
):
    acc = await session.get(FinanceAccount, req.account_id)
    if not acc:
        raise HTTPException(400, "账户不存在")
    cat = await session.get(FinanceCategory, req.category_id)
    if not cat:
        raise HTTPException(400, "科目不存在")
    if cat.type != req.type:
        raise HTTPException(400, f"科目类型({cat.type})与流水类型({req.type})不符")

    tx = FinanceTransaction(
        type=req.type, amount=req.amount, account_id=req.account_id,
        category_id=req.category_id, dept_id=req.dept_id, user_id=user.id,
        transaction_date=req.transaction_date, remark=req.remark,
    )
    session.add(tx)
    # 联动账户余额：收入+，支出-
    delta = req.amount if req.type == "income" else -req.amount
    acc.balance = (acc.balance or Decimal("0")) + delta
    await session.commit()
    await session.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.get("")
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str = Query(None),
    account_id: int = Query(None),
    category_id: int = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:transaction:save")),
):
    stmt = select(FinanceTransaction)
    if type:
        stmt = stmt.where(FinanceTransaction.type == type)
    if account_id:
        stmt = stmt.where(FinanceTransaction.account_id == account_id)
    if category_id:
        stmt = stmt.where(FinanceTransaction.category_id == category_id)
    if start_date:
        stmt = stmt.where(FinanceTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(FinanceTransaction.transaction_date <= end_date)
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(
            stmt.order_by(FinanceTransaction.transaction_date.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [TransactionOut.model_validate(t).model_dump() for t in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.delete("/{tid}")
async def delete_transaction(
    tid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:transaction:save")),
):
    tx = await session.get(FinanceTransaction, tid)
    if not tx:
        raise HTTPException(404, "流水不存在")
    # 反向调整账户余额
    acc = await session.get(FinanceAccount, tx.account_id)
    if acc:
        delta = -tx.amount if tx.type == "income" else tx.amount
        acc.balance = (acc.balance or Decimal("0")) + delta
    await session.delete(tx)
    await session.commit()
    return {"success": True}
