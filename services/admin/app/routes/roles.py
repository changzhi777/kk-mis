"""角色管理路由（含权限分配）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import require_permission
from ..models import Role, role_permissions
from ..schemas.enterprise import RoleCreate, RoleOut, RoleUpdate

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


async def _role_permission_ids(role_id: int, session: AsyncSession) -> list[int]:
    rows = (
        await session.execute(
            select(role_permissions.c.permission_id).where(
                role_permissions.c.role_id == role_id
            )
        )
    ).scalars().all()
    return list(rows)


@router.get("")
async def list_roles(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:role:save")),
):
    roles = (
        await session.execute(select(Role).order_by(Role.sort))
    ).scalars().all()
    items = []
    for r in roles:
        d = RoleOut.model_validate(r).model_dump()
        d["permission_ids"] = await _role_permission_ids(r.id, session)
        items.append(d)
    return {"items": items}


@router.post("", response_model=RoleOut)
async def create_role(
    req: RoleCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:role:save")),
):
    if (
        await session.execute(select(Role).where(Role.code == req.code))
    ).scalar_one_or_none():
        raise HTTPException(400, "角色编码已存在")
    r = Role(
        code=req.code, name=req.name, sort=req.sort, status=req.status,
        data_scope=req.data_scope, remark=req.remark,
    )
    session.add(r)
    await session.flush()
    for pid in req.permission_ids:
        await session.execute(role_permissions.insert().values(role_id=r.id, permission_id=pid))
    await session.commit()
    await session.refresh(r)
    return RoleOut.model_validate(r)


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    req: RoleUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:role:save")),
):
    r = await session.get(Role, role_id)
    if not r:
        raise HTTPException(404, "角色不存在")
    r.name = req.name
    r.sort = req.sort
    r.status = req.status
    r.data_scope = req.data_scope
    r.remark = req.remark
    # 重建权限关联
    await session.execute(role_permissions.delete().where(role_permissions.c.role_id == role_id))
    for pid in (req.permission_ids or []):
        await session.execute(role_permissions.insert().values(role_id=role_id, permission_id=pid))
    await session.commit()
    await session.refresh(r)
    return RoleOut.model_validate(r)


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:role:save")),
):
    r = await session.get(Role, role_id)
    if not r:
        raise HTTPException(404, "角色不存在")
    if r.code == "super_admin":
        raise HTTPException(400, "不可删除超级管理员角色")
    await session.delete(r)
    await session.commit()
    return {"success": True}
