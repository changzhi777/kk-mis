"""CMS 评论路由（公开提交 + admin 审核）

- POST /reviews：公开提交（产品须 published，提交后 pending 待审）
- GET /reviews：admin 列表（按 status 过滤）
- GET /reviews/export：CSV 导出
- PUT /reviews/{id}/status：admin 审核（pending/approved/rejected）
- DELETE /reviews/{id}：admin 删除
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Review, TourProduct
from ...schemas.cms import ReviewCreate, ReviewOut, ReviewStatusUpdate
from ...utils import to_csv

router = APIRouter(prefix="/api/v1/cms/reviews", tags=["cms-review"])


@router.post("")
async def submit_review(req: ReviewCreate, session: AsyncSession = Depends(get_session)):
    """公开提交评论（需产品 published，提交后 pending 待审）"""
    p = await session.get(TourProduct, req.product_id)
    if not p or p.status != "published":
        raise HTTPException(400, "产品不存在或未发布")
    review = Review(**req.model_dump(), status="pending")
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return ReviewOut.model_validate(review).model_dump()


@router.get("")
async def list_reviews(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:review:list")),
):
    q = select(Review).order_by(Review.id.desc())
    if status:
        q = q.where(Review.status == status)
    items = (await session.execute(q)).scalars().all()
    return {"items": [ReviewOut.model_validate(r).model_dump() for r in items]}


@router.get("/export")
async def export_reviews(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:review:list")),
):
    """导出评论 CSV"""
    q = select(Review).order_by(Review.id.desc())
    if status:
        q = q.where(Review.status == status)
    items = (await session.execute(q)).scalars().all()
    rows = [
        [r.id, r.product_id, r.author_name, r.rating, r.content, r.status, r.created_at.isoformat() if r.created_at else ""]
        for r in items
    ]
    cols = [("id", "ID"), ("product_id", "产品ID"), ("author_name", "昵称"), ("rating", "评分"), ("content", "内容"), ("status", "状态"), ("created_at", "时间")]
    return StreamingResponse(
        io.BytesIO(to_csv(rows, cols)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cms_reviews.csv"'},
    )


@router.put("/{review_id}/status")
async def update_review_status(
    review_id: int,
    req: ReviewStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:review:save")),
):
    # MEDIUM：审核状态白名单（防非法值写入）
    valid = {"pending", "approved", "rejected"}
    if req.status not in valid:
        raise HTTPException(400, f"非法状态，允许: {sorted(valid)}")
    r = await session.get(Review, review_id)
    if not r:
        raise HTTPException(404, "评论不存在")
    r.status = req.status
    await session.commit()
    await session.refresh(r)
    return ReviewOut.model_validate(r).model_dump()


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:review:save")),
):
    r = await session.get(Review, review_id)
    if not r:
        raise HTTPException(404, "评论不存在")
    await session.delete(r)
    await session.commit()
    return {"success": True}
