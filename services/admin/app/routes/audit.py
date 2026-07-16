"""审计日志查看"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import require_permission
from ..models import AuditLog, User

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    method: str = Query(None),
    path: str = Query(None),
    user_id: int = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:audit:view")),
):
    stmt = select(AuditLog)
    if method:
        stmt = stmt.where(AuditLog.method == method)
    if path:
        if len(path) > 200:  # MEDIUM：防超长子串 DoS
            raise HTTPException(400, "path 查询过长（≤200）")
        stmt = stmt.where(AuditLog.path.contains(path))
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(
            stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    # 批量取 username
    uids = {i.user_id for i in items if i.user_id}
    names = {}
    if uids:
        rows = (
            await session.execute(select(User.id, User.username).where(User.id.in_(uids)))
        ).all()
        names = {r[0]: r[1] for r in rows}
    return {
        "items": [
            {
                **{k: getattr(it, k) for k in ("id", "user_id", "method", "path", "status_code", "ip", "duration_ms")},
                "username": names.get(it.user_id),
                "created_at": it.created_at.isoformat() if it.created_at else None,
            }
            for it in items
        ],
        "total": total,
    }
