"""审批：流程定义 + 我的申请 + 待审批 + approve/reject"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, require_permission
from ...models import ApprovalFlow, ApprovalInstance, ApprovalRecord, User
from ...schemas.oa import (
    ApprovalFlowCreate,
    ApprovalFlowOut,
    ApprovalInstanceOut,
    ApprovalRecordOut,
    ApproveRequest,
)
from ...services.approval_engine import approve as do_approve, reject as do_reject

router = APIRouter(prefix="/api/v1/oa/approvals", tags=["oa-approval"])


@router.get("/flows")
async def list_flows(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:approval:save")),
):
    flows = (
        await session.execute(select(ApprovalFlow).order_by(ApprovalFlow.id))
    ).scalars().all()
    return {"items": [ApprovalFlowOut.model_validate(f).model_dump() for f in flows]}


@router.post("/flows", response_model=ApprovalFlowOut)
async def create_flow(
    req: ApprovalFlowCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:approval:save")),
):
    f = ApprovalFlow(**req.model_dump())
    session.add(f)
    await session.commit()
    await session.refresh(f)
    return ApprovalFlowOut.model_validate(f)


@router.get("/instances/mine")
async def my_instances(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    insts = (
        await session.execute(
            select(ApprovalInstance)
            .where(ApprovalInstance.applicant_id == user.id)
            .order_by(ApprovalInstance.id.desc())
        )
    ).scalars().all()
    return {"items": [ApprovalInstanceOut.model_validate(i).model_dump() for i in insts]}


@router.get("/instances/pending")
async def pending_instances(
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    insts = (
        await session.execute(
            select(ApprovalInstance)
            .where(ApprovalInstance.status == "pending")
            .order_by(ApprovalInstance.id.desc())
        )
    ).scalars().all()
    return {"items": [ApprovalInstanceOut.model_validate(i).model_dump() for i in insts]}


@router.post("/instances/{iid}/approve")
async def approve_instance(
    iid: int,
    req: ApproveRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    inst, err = await do_approve(session, iid, user.id, req.comment)
    if err:
        raise HTTPException(400, err)
    await session.commit()
    return {"success": True, "status": inst.status}


@router.post("/instances/{iid}/reject")
async def reject_instance(
    iid: int,
    req: ApproveRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    inst, err = await do_reject(session, iid, user.id, req.comment)
    if err:
        raise HTTPException(400, err)
    await session.commit()
    return {"success": True, "status": inst.status}


@router.get("/instances/{iid}/records")
async def instance_records(
    iid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    records = (
        await session.execute(
            select(ApprovalRecord)
            .where(ApprovalRecord.instance_id == iid)
            .order_by(ApprovalRecord.node)
        )
    ).scalars().all()
    return {"items": [ApprovalRecordOut.model_validate(r).model_dump() for r in records]}
