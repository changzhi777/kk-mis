"""权限管理路由（树形 + flat + CRUD）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import require_permission
from ..models import Permission
from ..schemas.enterprise import PermissionCreate, PermissionOut, PermissionUpdate

router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])


def _build_tree(perms):
    """flat 列表 → 树"""
    by_id = {p.id: PermissionOut.model_validate(p) for p in perms}
    roots = []
    for p in perms:
        node = by_id[p.id]
        if p.parent_id and p.parent_id in by_id:
            by_id[p.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.get("/tree")
async def permission_tree(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:permission:save")),
):
    perms = (
        await session.execute(select(Permission).order_by(Permission.sort, Permission.id))
    ).scalars().all()
    return {"tree": _build_tree(perms)}


@router.get("/flat")
async def permission_flat(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:permission:save")),
):
    perms = (
        await session.execute(select(Permission).order_by(Permission.sort, Permission.id))
    ).scalars().all()
    return {"items": [PermissionOut.model_validate(p).model_dump() for p in perms]}


@router.post("", response_model=PermissionOut)
async def create_permission(
    req: PermissionCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:permission:save")),
):
    if (
        await session.execute(select(Permission).where(Permission.code == req.code))
    ).scalar_one_or_none():
        raise HTTPException(400, "权限编码已存在")
    p = Permission(**req.model_dump())
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return PermissionOut.model_validate(p)


@router.put("/{pid}", response_model=PermissionOut)
async def update_permission(
    pid: int,
    req: PermissionUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:permission:save")),
):
    p = await session.get(Permission, pid)
    if not p:
        raise HTTPException(404, "权限不存在")
    for k, v in req.model_dump().items():
        setattr(p, k, v)
    await session.commit()
    await session.refresh(p)
    return PermissionOut.model_validate(p)


@router.delete("/{pid}")
async def delete_permission(
    pid: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:permission:save")),
):
    p = await session.get(Permission, pid)
    if not p:
        raise HTTPException(404, "权限不存在")
    children = (
        await session.execute(select(Permission).where(Permission.parent_id == pid))
    ).scalars().all()
    if children:
        raise HTTPException(400, "存在子节点，请先删除子节点")
    await session.delete(p)
    await session.commit()
    return {"success": True}
