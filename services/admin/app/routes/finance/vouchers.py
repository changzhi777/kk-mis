"""记账凭证路由（复式，Voucher + JournalEntry，借贷平衡）。

2026-07-15 标准复式记账 Phase 2：
- POST /vouchers：创建凭证（草稿）+ 分录，校验 Σdebit = Σcredit
- POST /vouchers/{id}/post：过账 → 更新各账户余额（balance += debit - credit）
"""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import FinanceAccount, JournalEntry, User, Voucher
from ...utils import utcnow

router = APIRouter(prefix="/api/v1/finance/vouchers", tags=["finance-voucher"])


class EntryIn(BaseModel):
    account_id: int
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    summary: str | None = None


class VoucherCreate(BaseModel):
    voucher_date: datetime
    summary: str | None = None
    entries: list[EntryIn]


@router.post("")
async def create_voucher(
    req: VoucherCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("finance:transaction:save")),
):
    """创建凭证（草稿）+ 分录，校验借贷平衡（Σdebit = Σcredit）。"""
    if len(req.entries) < 2:
        raise HTTPException(400, "至少 2 条分录（一借一贷）")
    total_d = sum((e.debit for e in req.entries), Decimal("0"))
    total_c = sum((e.credit for e in req.entries), Decimal("0"))
    if total_d != total_c:
        raise HTTPException(400, f"借贷不平：借 {total_d} ≠ 贷 {total_c}")
    # 校验账户存在
    for e in req.entries:
        if not await session.get(FinanceAccount, e.account_id):
            raise HTTPException(400, f"账户 {e.account_id} 不存在")
    # 凭证号：记-日期-序号
    seq = (await session.execute(select(func.count()).select_from(Voucher))).scalar_one() + 1
    number = f"记-{req.voucher_date.strftime('%Y%m%d')}-{seq:03d}"
    v = Voucher(
        number=number,
        voucher_date=req.voucher_date,
        summary=req.summary,
        status="draft",
        created_by=user.id,
    )
    session.add(v)
    await session.flush()
    for e in req.entries:
        session.add(
            JournalEntry(
                voucher_id=v.id,
                account_id=e.account_id,
                debit=e.debit,
                credit=e.credit,
                summary=e.summary,
            )
        )
    await session.commit()
    await session.refresh(v)
    return {
        "id": v.id,
        "number": v.number,
        "status": v.status,
        "debit_total": float(total_d),
        "credit_total": float(total_c),
    }


@router.post("/{vid}/post")
async def post_voucher(
    vid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:transaction:save")),
):
    """过账：校验平衡 → 更新账户余额（balance += debit - credit）→ status=posted。"""
    v = await session.get(Voucher, vid)
    if not v:
        raise HTTPException(404, "凭证不存在")
    if v.status == "posted":
        raise HTTPException(400, "已过账")
    entries = (
        await session.execute(select(JournalEntry).where(JournalEntry.voucher_id == vid))
    ).scalars().all()
    total_d = sum((e.debit for e in entries), Decimal("0"))
    total_c = sum((e.credit for e in entries), Decimal("0"))
    if total_d != total_c:
        raise HTTPException(400, f"借贷不平，无法过账：借 {total_d} ≠ 贷 {total_c}")
    # 复式余额：balance = Σ(debit - credit)，报表按 account_type 解释方向
    for e in entries:
        acc = await session.get(FinanceAccount, e.account_id)
        if acc:
            acc.balance = (acc.balance or Decimal("0")) + e.debit - e.credit
    v.status = "posted"
    v.posted_at = utcnow()
    await session.commit()
    return {"success": True, "voucher_id": vid, "posted": True}


@router.get("")
async def list_vouchers(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("finance:transaction:save")),
):
    """凭证列表（含分录）。"""
    stmt = select(Voucher)
    if status:
        stmt = stmt.where(Voucher.status == status)
    vouchers = (await session.execute(stmt.order_by(Voucher.id.desc()))).scalars().all()
    # 批量查分录（避免 N+1，2026-07-15 优化）
    vids = [v.id for v in vouchers]
    all_entries = (
        (
            await session.execute(
                select(JournalEntry).where(JournalEntry.voucher_id.in_(vids))
            )
        ).scalars().all()
        if vids
        else []
    )
    by_voucher: dict[int, list] = {}
    for e in all_entries:
        by_voucher.setdefault(e.voucher_id, []).append(e)
    result = []
    for v in vouchers:
        entries = by_voucher.get(v.id, [])
        result.append({
            "id": v.id,
            "number": v.number,
            "voucher_date": v.voucher_date.isoformat() if v.voucher_date else None,
            "summary": v.summary,
            "status": v.status,
            "entries": [
                {
                    "account_id": e.account_id,
                    "debit": float(e.debit),
                    "credit": float(e.credit),
                    "summary": e.summary,
                }
                for e in entries
            ],
        })
    return {"items": result}
