"""审批工作流引擎（流转 + 记录 + 业务状态同步）"""
import json

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApprovalFlow, ApprovalInstance, ApprovalRecord, LeaveRequest


async def create_instance(
    session: AsyncSession, flow_id: int, applicant_id: int,
    business_type: str, business_id: int,
) -> ApprovalInstance:
    """创建审批实例（current_node=0, pending）"""
    inst = ApprovalInstance(
        flow_id=flow_id, applicant_id=applicant_id,
        business_type=business_type, business_id=business_id,
        status="pending", current_node=0,
    )
    session.add(inst)
    await session.flush()
    return inst


async def _update_business(session: AsyncSession, btype: str, bid: int, status: str):
    """审批完成后同步业务表状态"""
    if btype == "leave":
        lr = await session.get(LeaveRequest, bid)
        if lr:
            lr.status = status


async def approve(
    session: AsyncSession, instance_id: int, approver_id: int, comment: str = None
):
    """审批通过：推进节点，到末尾则完成"""
    inst = await session.get(ApprovalInstance, instance_id)
    if not inst or inst.status != "pending":
        return None, "实例不存在或已结束"
    flow = await session.get(ApprovalFlow, inst.flow_id)
    nodes = json.loads(flow.nodes_config)
    session.add(
        ApprovalRecord(
            instance_id=inst.id, node=inst.current_node,
            approver_id=approver_id, action="approve", comment=comment,
        )
    )
    inst.current_node += 1
    if inst.current_node >= len(nodes):
        inst.status = "approved"
        await _update_business(session, inst.business_type, inst.business_id, "approved")
    return inst, None


async def reject(
    session: AsyncSession, instance_id: int, approver_id: int, comment: str = None
):
    """驳回：实例 + 业务都 rejected"""
    inst = await session.get(ApprovalInstance, instance_id)
    if not inst or inst.status != "pending":
        return None, "实例不存在或已结束"
    session.add(
        ApprovalRecord(
            instance_id=inst.id, node=inst.current_node,
            approver_id=approver_id, action="reject", comment=comment,
        )
    )
    inst.status = "rejected"
    await _update_business(session, inst.business_type, inst.business_id, "rejected")
    return inst, None
