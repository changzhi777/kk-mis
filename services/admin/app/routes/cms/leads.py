"""CMS 询价线索路由（订制游 A）

- POST /leads：公开提交（无需登录，终端用户填表）
- GET /leads：admin 列表（按 status 过滤，需权限）
- GET /leads/export：CSV 导出
- PUT /leads/{id}/status：admin 状态流转（new→contacted→converted/closed）
- DELETE /leads/{id}：admin 删除
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import InquiryLead
from ...schemas.cms import InquiryLeadCreate, InquiryLeadOut, InquiryLeadStatusUpdate
from ...services.notifier import notify
from ...utils import to_csv

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
    # webhook 通知新线索（旁路）
    await notify(
        "新询价线索",
        {"name": req.name, "phone": req.phone, "destination": req.destination, "people": req.people},
    )
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


@router.get("/export")
async def export_leads(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:lead:list")),
):
    """导出线索 CSV"""
    q = select(InquiryLead).order_by(InquiryLead.id.desc())
    if status:
        q = q.where(InquiryLead.status == status)
    items = (await session.execute(q)).scalars().all()
    rows = [
        [
            l.id, l.name, l.phone, l.wechat or "", l.destination or "",
            l.travel_date or "", l.people or "", l.budget or "", l.status,
            l.created_at.isoformat() if l.created_at else "",
        ]
        for l in items
    ]
    cols = [
        ("id", "ID"), ("name", "联系人"), ("phone", "电话"), ("wechat", "微信"),
        ("destination", "目的地"), ("travel_date", "出行日期"), ("people", "人数"),
        ("budget", "预算"), ("status", "状态"), ("created_at", "时间"),
    ]
    return StreamingResponse(
        io.BytesIO(to_csv(rows, cols)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cms_leads.csv"'},
    )


@router.put("/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    req: InquiryLeadStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:lead:save")),
):
    """线索状态流转（new/contacted/converted/closed）"""
    # MEDIUM：状态流转白名单（防非法值写入）
    valid = {"new", "contacted", "converted", "closed"}
    if req.status not in valid:
        raise HTTPException(400, f"非法状态，允许: {sorted(valid)}")
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
