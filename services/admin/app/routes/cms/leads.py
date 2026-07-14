"""CMS 询价线索路由（订制游 A）

- POST /leads：公开提交（无需登录，终端用户填表）
- GET /leads：admin 列表（按 status 过滤，需权限）
- PUT /leads/{id}/status：admin 状态流转（new→contacted→converted/closed）
- DELETE /leads/{id}：admin 删除
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import InquiryLead
from ...schemas.cms import InquiryLeadCreate, InquiryLeadOut, InquiryLeadStatusUpdate

router = APIRouter(prefix="/api/v1/cms/leads", tags=["cms-lead"])


@router.post("")
async def submit_lead(
    req: InquiryLeadCreate,
    session: AsyncSession = Depends(get_session),
):
    """公开提交询价线索（无需登录）"""
    lead = InquiryLead(**req.model_dump(exclude_none=True), status="new")
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return InquiryLeadOut.model_validate(lead).model_dump()


@router.get("")
async def list_leads(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:lead:list")),
):
    """线索列表（admin，按 status 过滤）"""
    q = select(InquiryLead).order_by(InquiryLead.id.desc())
    if status:
        q = q.where(InquiryLead.status == status)
    items = (await session.execute(q)).scalars().all()
    return {"items": [InquiryLeadOut.model_validate(l).model_dump() for l in items]}


@router.put("/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    req: InquiryLeadStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:lead:save")),
):
    """线索状态流转（new/contacted/converted/closed）"""
    lead = await session.get(InquiryLead, lead_id)
    if not lead:
        raise HTTPException(404, "线索不存在")
    lead.status = req.status
    await session.commit()
    await session.refresh(lead)
    return InquiryLeadOut.model_validate(lead).model_dump()


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:lead:save")),
):
    lead = await session.get(InquiryLead, lead_id)
    if not lead:
        raise HTTPException(404, "线索不存在")
    await session.delete(lead)
    await session.commit()
    return {"success": True}
