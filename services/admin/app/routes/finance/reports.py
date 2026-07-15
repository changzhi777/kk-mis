"""财务报表：收支汇总 + 按科目聚合"""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import FinanceAccount, FinanceCategory, FinanceTransaction

router = APIRouter(prefix="/api/v1/finance/reports", tags=["finance-report"])


async def _ledger_accounts(session: AsyncSession) -> list:
    """取所有标准科目（含 code，复式 3 报表共用，DRY）。"""
    return (
        await session.execute(
            select(FinanceAccount).where(FinanceAccount.code.is_not(None))
        )
    ).scalars().all()


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


@router.get("/by-account")
async def by_account(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """按账户聚合：各账户收入/支出/结余"""
    stmt = (
        select(
            FinanceAccount.id,
            FinanceAccount.name,
            FinanceTransaction.type,
            func.sum(FinanceTransaction.amount),
        )
        .join(FinanceAccount, FinanceAccount.id == FinanceTransaction.account_id)
    )
    if start_date:
        stmt = stmt.where(FinanceTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(FinanceTransaction.transaction_date <= end_date)
    stmt = stmt.group_by(FinanceAccount.id, FinanceTransaction.type)
    rows = (await session.execute(stmt)).all()
    accs: dict[int, dict] = {}
    for aid, name, t, amt in rows:
        if aid not in accs:
            accs[aid] = {"account_id": aid, "account": name, "income": 0.0, "expense": 0.0}
        if t == "income":
            accs[aid]["income"] += float(amt or 0)
        else:
            accs[aid]["expense"] += float(amt or 0)
    items = [{"balance": a["income"] - a["expense"], **a} for a in accs.values()]
    return {"items": items}


@router.get("/by-month")
async def by_month(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """按月聚合收入/支出（趋势图数据源，跨 DB 用 Python 聚合避开 strftime/extract 差异）"""
    stmt = select(
        FinanceTransaction.type,
        FinanceTransaction.transaction_date,
        FinanceTransaction.amount,
    )
    if start_date:
        stmt = stmt.where(FinanceTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(FinanceTransaction.transaction_date <= end_date)
    rows = (await session.execute(stmt)).all()
    months: dict[str, dict] = {}
    for t, d, amt in rows:
        ym = d.strftime("%Y-%m") if d else "unknown"
        if ym not in months:
            months[ym] = {"month": ym, "income": 0.0, "expense": 0.0}
        if t == "income":
            months[ym]["income"] += float(amt or 0)
        else:
            months[ym]["expense"] += float(amt or 0)
    items = [{"balance": m["income"] - m["expense"], **m} for m in months.values()]
    items.sort(key=lambda x: x["month"])
    return {"items": items}


@router.get("/trial-balance")
async def trial_balance(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """试算平衡表：各账户借贷余额汇总（Σ借应等于Σ贷，复式记账核心校验）。"""
    accounts = sorted(await _ledger_accounts(session), key=lambda a: a.code or "")
    items = []
    total_d = Decimal("0")
    total_c = Decimal("0")
    for a in accounts:
        bal = a.balance or Decimal("0")
        if bal >= 0:  # 借方余额
            items.append({"code": a.code, "name": a.name, "account_type": a.account_type, "debit": float(bal), "credit": 0.0})
            total_d += bal
        else:
            items.append({"code": a.code, "name": a.name, "account_type": a.account_type, "debit": 0.0, "credit": float(-bal)})
            total_c += -bal
    return {
        "items": items,
        "total_debit": float(total_d),
        "total_credit": float(total_c),
        "balanced": total_d == total_c,
    }


@router.get("/balance-sheet")
async def balance_sheet(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """资产负债表：资产 = 负债 + 权益（会计第一恒等式）。"""
    accounts = await _ledger_accounts(session)
    assets = Decimal("0")
    liabilities = Decimal("0")
    equity = Decimal("0")
    expenses = Decimal("0")
    revenue = Decimal("0")
    for a in accounts:
        bal = a.balance or Decimal("0")
        if a.account_type == "asset":
            assets += bal
        elif a.account_type == "liability":
            liabilities += -bal
        elif a.account_type == "equity":
            equity += -bal
        elif a.account_type == "expense":
            expenses += bal  # 借方
        elif a.account_type == "revenue":
            revenue += -bal  # 贷方
    # 扩展会计等式（结转前）：assets + expense = liabilities + equity + revenue
    return {
        "assets": float(assets),
        "liabilities": float(liabilities),
        "equity": float(equity),
        "expenses": float(expenses),
        "revenue": float(revenue),
        "profit": float(revenue - expenses),
        "balanced": (assets + expenses) == (liabilities + equity + revenue),
    }


@router.get("/income-statement")
async def income_statement(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:report:view")),
):
    """利润表：收入 − 支出 = 利润。"""
    accounts = await _ledger_accounts(session)
    revenue = Decimal("0")
    expense = Decimal("0")
    for a in accounts:
        bal = a.balance or Decimal("0")
        if a.account_type == "revenue":
            revenue += -bal  # 贷方余额
        elif a.account_type == "expense":
            expense += bal  # 借方余额
    profit = revenue - expense
    return {
        "revenue": float(revenue),
        "expense": float(expense),
        "profit": float(profit),
    }
