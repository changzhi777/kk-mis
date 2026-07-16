"""用户管理路由"""
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import require_permission
from .. import cache
from ..models import Role, User, user_roles
from ..schemas.enterprise import UserCreate, UserOut, UserResetPassword, UserUpdate
from ..utils import to_csv
from ..security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])


async def _attach_roles(user: User, session: AsyncSession):
    """给 User 对象附加 role_ids（UserOut 用）"""
    rids = (
        await session.execute(
            select(user_roles.c.role_id).where(user_roles.c.user_id == user.id)
        )
    ).scalars().all()
    user.role_ids = list(rids)
    return user


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:list")),
):
    stmt = select(User)
    if keyword:
        stmt = stmt.where(
            or_(User.username.contains(keyword), User.name.contains(keyword))
        )
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    users = (
        await session.execute(
            stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    for u in users:
        await _attach_roles(u, session)
    return {
        "items": [UserOut.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/export")
async def export_users(
    keyword: str = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:list")),
):
    """导出用户列表为 CSV"""
    stmt = select(User)
    if keyword:
        stmt = stmt.where(or_(User.username.contains(keyword), User.name.contains(keyword)))
    users = (await session.execute(stmt.order_by(User.id.desc()))).scalars().all()
    # 预加载角色名 + 用户-角色映射（避免 N+1）
    role_names = {r.id: r.name for r in (await session.execute(select(Role))).scalars().all()}
    ur_rows = (await session.execute(select(user_roles.c.user_id, user_roles.c.role_id))).all()
    user_roles_map: dict[int, list[int]] = {}
    for uid, rid in ur_rows:
        user_roles_map.setdefault(uid, []).append(rid)
    rows = [{
        "id": u.id,
        "username": u.username,
        "name": u.name or "",
        "email": u.email or "",
        "phone": u.phone or "",
        "roles": "、".join(role_names.get(rid, "") for rid in user_roles_map.get(u.id, [])),
        "status": "启用" if u.status else "禁用",
    } for u in users]
    cols = [("id", "ID"), ("username", "用户名"), ("name", "姓名"),
            ("email", "邮箱"), ("phone", "手机"), ("roles", "角色"), ("status", "状态")]
    data = to_csv(rows, cols)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="users.csv"'},
    )


@router.post("", response_model=UserOut)
async def create_user(
    req: UserCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:save")),
):
    if (
        await session.execute(select(User).where(User.username == req.username))
    ).scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    u = User(
        username=req.username,
        password_hash=hash_password(req.password),
        name=req.name,
        email=req.email,
        phone=req.phone,
        dept_id=req.dept_id,
        status=req.status,
    )
    session.add(u)
    await session.flush()
    for rid in req.role_ids:
        await session.execute(user_roles.insert().values(user_id=u.id, role_id=rid))
    await session.commit()
    await session.refresh(u)
    await _attach_roles(u, session)
    return UserOut.model_validate(u)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    req: UserUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:save")),
):
    u = await session.get(User, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    for k in ("name", "email", "phone", "dept_id"):
        v = getattr(req, k)
        if v is not None:
            setattr(u, k, v)
    if req.status is not None:
        u.status = req.status
    if req.role_ids is not None:
        await session.execute(user_roles.delete().where(user_roles.c.user_id == user_id))
        for rid in req.role_ids:
            await session.execute(user_roles.insert().values(user_id=user_id, role_id=rid))
    await session.commit()
    if req.role_ids is not None:
        await cache.invalidate_user(user_id)  # 角色变更 → 失效权限/菜单缓存
    await session.refresh(u)
    await _attach_roles(u, session)
    return UserOut.model_validate(u)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:remove")),
):
    u = await session.get(User, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    if u.username == "admin":
        raise HTTPException(400, "不可删除超级管理员")
    await session.delete(u)
    await session.commit()
    await cache.invalidate_user(user_id)  # MEDIUM：删用户失效权限/菜单缓存（原漏）
    return {"success": True}


@router.put("/{user_id}/password")
async def reset_password(
    user_id: int,
    req: UserResetPassword,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:user:save")),
):
    u = await session.get(User, user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    u.password_hash = hash_password(req.password)
    await session.commit()
    return {"success": True, "message": "密码已重置"}
