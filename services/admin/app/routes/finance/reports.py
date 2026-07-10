"""财务报表：收支汇总 + 按科目聚合"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import FinanceCategory, FinanceTransaction

router = APIRouter(prefix="/api/v1/finance/reports", tags=["finance-report"])


@router.get("/summary")
async def summary(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """收支汇总：总收入 / 总支出 / 结余"""
    stmt = select(FinanceTransaction.type, func.sum(FinanceTransaction.amount))
    if start_date:
        stmt = stmt.where(FinanceTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(FinanceTransaction.transaction_date <= end_date)
    stmt = stmt.group_by(FinanceTransaction.type)
    rows = (await session.execute(stmt)).all()
    income = sum((r[1] for r in rows if r[0] == "income"), start=Decimal("0"))
    expense = sum((r[1] for r in rows if r[0] == "expense"), start=Decimal("0"))
    return {
        "income": float(income),
        "expense": float(expense),
        "balance": float(income - expense),
        "count": sum(1 for _ in rows),
    }


@router.get("/by-category")
async def by_category(
    type: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """按科目聚合（金额降序）"""
    stmt = (
        select(
            FinanceCategory.name,
            FinanceTransaction.type,
            func.sum(FinanceTransaction.amount),
            func.count(),
        )
        .join(FinanceCategory, FinanceCategory.id == FinanceTransaction.category_id)
    )
    if type:
        stmt = stmt.where(FinanceTransaction.type == type)
    if start_date:
        stmt = stmt.where(FinanceTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(FinanceTransaction.transaction_date <= end_date)
    stmt = stmt.group_by(FinanceCategory.id, FinanceTransaction.type).order_by(
        func.sum(FinanceTransaction.amount).desc()
    )
    rows = (await session.execute(stmt)).all()
    return {
        "items": [
            {"category": r[0], "type": r[1], "amount": float(r[2]), "count": r[3]}
            for r in rows
        ]
    }


# 占位，避免未导入 Decimal（summary 中用到）
from decimal import Decimal  # noqa: E402
