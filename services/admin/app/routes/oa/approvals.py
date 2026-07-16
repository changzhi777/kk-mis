"""审批：流程定义 + 我的申请 + 待审批 + approve/reject"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, get_user_permissions, is_super_admin, require_permission
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
    user: User = Depends(get_current_user),
):
    insts = (
        await session.execute(
            select(ApprovalInstance)
            .where(ApprovalInstance.status == "pending")
            .order_by(ApprovalInstance.id.desc())
        )
    ).scalars().all()
    # IDOR 防护：超管 / 持 oa:approval:save 权限者可看全部 pending；
    # 其他用户仅看“当前节点审批人 = 自己”的实例（user 节点精确匹配 approver_id；
    # leader 节点按 approval_engine 语义允许任意登录用户审，故也可见）
    if not await is_super_admin(user, session):
        codes = await get_user_permissions(user.id, session)
        if "oa:approval:save" not in codes:
            filtered = []
            for inst in insts:
                flow = await session.get(ApprovalFlow, inst.flow_id)
                if not flow:
                    continue
                try:
                    nodes = json.loads(flow.nodes_config)
                except (json.JSONDecodeError, TypeError):
                    continue
                node = nodes[inst.current_node] if inst.current_node < len(nodes) else None
                if not node:
                    continue
                atype = node.get("approver_type")
                if atype == "user" and node.get("approver_id") == user.id:
                    filtered.append(inst)
                elif atype == "leader":
                    filtered.append(inst)
            insts = filtered
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
    user: User = Depends(get_current_user),
):
    inst = await session.get(ApprovalInstance, iid)
    if not inst:
        raise HTTPException(404, "审批实例不存在")
    # IDOR 防护：申请人 / 当前节点审批人 / 超管 可查审批轨迹；
    # 其他人 403（防任意用户枚举 iid 读他人审批记录）
    if inst.applicant_id != user.id and not await is_super_admin(user, session):
        flow = await session.get(ApprovalFlow, inst.flow_id)
        allowed = False
        if flow:
            try:
                nodes = json.loads(flow.nodes_config)
                node = nodes[inst.current_node] if inst.current_node < len(nodes) else None
                if node:
                    atype = node.get("approver_type")
                    if atype == "user" and node.get("approver_id") == user.id:
                        allowed = True
                    elif atype == "leader":
                        # leader 节点：任意登录用户可审（与 approval_engine 语义一致）
                        allowed = True
            except (json.JSONDecodeError, TypeError):
                pass
        if not allowed:
            raise HTTPException(403, "无权查看该审批记录")
    records = (
        await session.execute(
            select(ApprovalRecord)
            .where(ApprovalRecord.instance_id == iid)
            .order_by(ApprovalRecord.node)
        )
    ).scalars().all()
    return {"items": [ApprovalRecordOut.model_validate(r).model_dump() for r in records]}
