"""报销：提交触发审批 + 列表/详情"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import ApprovalFlow, ExpenseRequest, User
from ...schemas.oa import ExpenseCreate, ExpenseOut
from ...services.approval_engine import create_instance

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


@router.get("/{eid}", response_model=ExpenseOut)
async def get_expense(
    eid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    er = await session.get(ExpenseRequest, eid)
    if not er:
        raise HTTPException(404, "报销不存在")
    return ExpenseOut.model_validate(er)
