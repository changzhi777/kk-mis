"""报销：提交触发审批 + 列表/详情"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, is_super_admin
from ...models import ApprovalFlow, ExpenseRequest, User
from ...schemas.oa import ExpenseCreate, ExpenseOut
from ...services.approval_engine import create_instance
from ...utils import to_csv

router = APIRouter(prefix="/api/v1/oa/expenses", tags=["oa-expense"])


@router.post("", response_model=ExpenseOut)
async def create_expense(
    req: ExpenseCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    er = ExpenseRequest(
        user_id=user.id, amount=req.amount, category=req.category,
        expense_date=req.expense_date, reason=req.reason, status="pending",
    )
    session.add(er)
    await session.flush()
    flow = (
        await session.execute(
            select(ApprovalFlow).where(
                ApprovalFlow.business_type == "expense", ApprovalFlow.status.is_(True)
            ).limit(1)
        )
    ).scalar_one_or_none()
    if flow:
        inst = await create_instance(session, flow.id, user.id, "expense", er.id)
        er.instance_id = inst.id
    await session.commit()
    await session.refresh(er)
    return ExpenseOut.model_validate(er)


@router.get("")
async def list_expenses(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ers = (
        await session.execute(
            select(ExpenseRequest)
            .where(ExpenseRequest.user_id == user.id)
            .order_by(ExpenseRequest.id.desc())
        )
    ).scalars().all()
    return {"items": [ExpenseOut.model_validate(e).model_dump() for e in ers]}


@router.get("/export")
async def export_expenses(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """导出我的报销为 CSV"""
    ers = (
        await session.execute(
            select(ExpenseRequest)
            .where(ExpenseRequest.user_id == user.id)
            .order_by(ExpenseRequest.id.desc())
        )
    ).scalars().all()
    cat_map = {"travel": "差旅", "office": "办公", "entertainment": "招待", "other": "其他"}
    status_map = {"pending": "审批中", "approved": "已批准", "rejected": "已驳回"}
    rows = [{
        "id": e.id,
        "date": e.expense_date,
        "category": cat_map.get(e.category, e.category),
        "amount": e.amount,
        "reason": e.reason or "",
        "status": status_map.get(e.status, e.status),
    } for e in ers]
    cols = [("id", "ID"), ("date", "日期"), ("category", "类别"),
            ("amount", "金额"), ("reason", "事由"), ("status", "状态")]
    data = to_csv(rows, cols)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="expenses.csv"'},
    )


@router.get("/{eid}", response_model=ExpenseOut)
async def get_expense(
    eid: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    er = await session.get(ExpenseRequest, eid)
    if not er:
        raise HTTPException(404, "报销不存在")
    # IDOR 防护：仅本人或超管可查；他人报销 403（防 id 枚举越权）
    if er.user_id != user.id and not await is_super_admin(user, session):
        raise HTTPException(403, "无权查看该报销")
    return ExpenseOut.model_validate(er)
