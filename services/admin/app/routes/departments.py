"""部门管理路由（flat + CRUD，前端建树）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import require_permission
from ..models import Department
from ..schemas.enterprise import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter(prefix="/api/v1/departments", tags=["departments"])


@router.get("")
async def list_departments(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:dept:save")),
):
    depts = (
        await session.execute(select(Department).order_by(Department.sort, Department.id))
    ).scalars().all()
    return {"items": [DepartmentOut.model_validate(d).model_dump() for d in depts]}


@router.post("", response_model=DepartmentOut)
async def create_department(
    req: DepartmentCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:dept:save")),
):
    d = Department(**req.model_dump())
    session.add(d)
    await session.commit()
    await session.refresh(d)
    return DepartmentOut.model_validate(d)


@router.put("/{did}", response_model=DepartmentOut)
async def update_department(
    did: int,
    req: DepartmentUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:dept:save")),
):
    d = await session.get(Department, did)
    if not d:
        raise HTTPException(404, "部门不存在")
    for k, v in req.model_dump().items():
        setattr(d, k, v)
    await session.commit()
    await session.refresh(d)
    return DepartmentOut.model_validate(d)


@router.delete("/{did}")
async def delete_department(
    did: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:dept:save")),
):
    d = await session.get(Department, did)
    if not d:
        raise HTTPException(404, "部门不存在")
    children = (
        await session.execute(select(Department).where(Department.parent_id == did))
    ).scalars().all()
    if children:
        raise HTTPException(400, "存在子部门，请先删除子部门")
    await session.delete(d)
    await session.commit()
    return {"success": True}
