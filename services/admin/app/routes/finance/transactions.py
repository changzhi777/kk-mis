"""收支流水路由（⚠️ DEPRECATED 2026-07-15：复式记账 Voucher 上线后单式流水逐步废弃，新功能用 /vouchers）。

保留兼容旧数据/前端；新业务用 POST /api/v1/finance/vouchers（借贷平衡 + 过账）。

⚠️ MEDIUM 双轨余额漂移：本路由与 vouchers 都直接改 FinanceAccount.balance。
同一笔业务若同时记 transaction + voucher，余额会翻倍。迁移期勿混用同账户；
彻底解决随 transactions 废弃（见 P2 移除任务）。
"""
import io
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...utils import to_csv
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


@router.get("/export")
async def export_transactions(
    type: str = Query(None),
    account_id: int = Query(None),
    category_id: int = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:transaction:save")),
):
    """导出流水为 CSV（UTF-8 BOM，Excel 双击不乱码）"""
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
    items = (
        await session.execute(stmt.order_by(FinanceTransaction.transaction_date.desc()))
    ).scalars().all()
    # 预加载账户/科目名（避免 N+1）
    accs = {a.id: a.name for a in (await session.execute(select(FinanceAccount))).scalars().all()}
    cats = {c.id: c.name for c in (await session.execute(select(FinanceCategory))).scalars().all()}
    rows = [{
        "id": t.id,
        "date": t.transaction_date,
        "type": "收入" if t.type == "income" else "支出",
        "amount": t.amount,
        "account": accs.get(t.account_id, ""),
        "category": cats.get(t.category_id, ""),
        "remark": t.remark or "",
    } for t in items]
    cols = [("id", "ID"), ("date", "日期"), ("type", "类型"), ("amount", "金额"),
            ("account", "账户"), ("category", "科目"), ("remark", "备注")]
    data = to_csv(rows, cols)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )


@router.put("/{tid}", response_model=TransactionOut)
async def update_transaction(
    tid: int,
    req: TransactionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("finance:transaction:save")),
):
    """更新流水：反向旧余额 → 应用新余额（支持改账户/科目/金额/类型）"""
    tx = await session.get(FinanceTransaction, tid)
    if not tx:
        raise HTTPException(404, "流水不存在")
    acc = await session.get(FinanceAccount, req.account_id)
    if not acc:
        raise HTTPException(400, "账户不存在")
    cat = await session.get(FinanceCategory, req.category_id)
    if not cat:
        raise HTTPException(400, "科目不存在")
    if cat.type != req.type:
        raise HTTPException(400, f"科目类型({cat.type})与流水类型({req.type})不符")
    # 反向旧余额（旧账户，可能和新账户不同）
    old_acc = await session.get(FinanceAccount, tx.account_id)
    if old_acc:
        old_delta = -tx.amount if tx.type == "income" else tx.amount
        old_acc.balance = (old_acc.balance or Decimal("0")) + old_delta
    # 应用新余额
    new_delta = req.amount if req.type == "income" else -req.amount
    acc.balance = (acc.balance or Decimal("0")) + new_delta
    tx.type = req.type
    tx.amount = req.amount
    tx.account_id = req.account_id
    tx.category_id = req.category_id
    tx.dept_id = req.dept_id
    tx.transaction_date = req.transaction_date
    tx.remark = req.remark
    await session.commit()
    await session.refresh(tx)
    return TransactionOut.model_validate(tx)


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
