"""请假：提交触发审批实例 + 列表/详情"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, is_super_admin
from ...models import ApprovalFlow, LeaveRequest, User
from ...schemas.oa import LeaveCreate, LeaveOut
from ...services.approval_engine import create_instance

router = APIRouter(prefix="/api/v1/oa/leaves", tags=["oa-leave"])


@router.post("", response_model=LeaveOut)
async def create_leave(
    req: LeaveCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """提交请假 → 自动创建审批实例"""
    lr = LeaveRequest(
        user_id=user.id, type=req.type, start_date=req.start_date,
        end_date=req.end_date, days=req.days, reason=req.reason, status="pending",
    )
    session.add(lr)
    await session.flush()
    # 查启用的请假流程
    flow = (
        await session.execute(
            select(ApprovalFlow).where(
                ApprovalFlow.business_type == "leave", ApprovalFlow.status.is_(True)
            ).limit(1)
        )
    ).scalar_one_or_none()
    if flow:
        inst = await create_instance(session, flow.id, user.id, "leave", lr.id)
        lr.instance_id = inst.id
    await session.commit()
    await session.refresh(lr)
    return LeaveOut.model_validate(lr)


@router.get("")
async def list_leaves(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    lrs = (
        await session.execute(
            select(LeaveRequest)
            .where(LeaveRequest.user_id == user.id)
            .order_by(LeaveRequest.id.desc())
        )
    ).scalars().all()
    return {"items": [LeaveOut.model_validate(l).model_dump() for l in lrs]}


@router.get("/{lid}", response_model=LeaveOut)
async def get_leave(
    lid: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    lr = await session.get(LeaveRequest, lid)
    if not lr:
        raise HTTPException(404, "请假不存在")
    # IDOR 防护：仅本人或超管可查；他人请假 403（防 id 枚举越权）
    if lr.user_id != user.id and not await is_super_admin(user, session):
        raise HTTPException(403, "无权查看该请假")
    return LeaveOut.model_validate(lr)
