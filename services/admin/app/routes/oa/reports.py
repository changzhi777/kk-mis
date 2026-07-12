"""工作汇报：提交 + 我的列表 + 全部查阅 + 标记已读（不走审批）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, require_permission
from ...models import User, WorkReport
from ...schemas.oa import ReportCreate, ReportOut

router = APIRouter(prefix="/api/v1/oa/reports", tags=["oa-report"])


@router.post("", response_model=ReportOut)
async def create_report(
    req: ReportCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """提交工作汇报"""
    r = WorkReport(
        user_id=user.id, type=req.type, period_start=req.period_start,
        period_end=req.period_end, content=req.content,
        plan_next=req.plan_next, problems=req.problems, status="submitted",
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return ReportOut.model_validate(r)


@router.get("")
async def list_my_reports(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """我的工作汇报"""
    rs = (
        await session.execute(
            select(WorkReport)
            .where(WorkReport.user_id == user.id)
            .order_by(WorkReport.id.desc())
        )
    ).scalars().all()
    return {"items": [ReportOut.model_validate(r).model_dump() for r in rs]}


@router.get("/all")
async def list_all_reports(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:report:view")),
):
    """查阅全部员工汇报（需 oa:report:view 权限）"""
    rs = (
        await session.execute(select(WorkReport).order_by(WorkReport.id.desc()))
    ).scalars().all()
    return {"items": [ReportOut.model_validate(r).model_dump() for r in rs]}


@router.get("/{rid}", response_model=ReportOut)
async def get_report(
    rid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    r = await session.get(WorkReport, rid)
    if not r:
        raise HTTPException(404, "汇报不存在")
    return ReportOut.model_validate(r)


@router.put("/{rid}/read")
async def mark_read(
    rid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("oa:report:view")),
):
    """标记已读"""
    r = await session.get(WorkReport, rid)
    if not r:
        raise HTTPException(404, "汇报不存在")
    r.status = "read"
    await session.commit()
    return {"id": rid, "status": "read"}
