"""CMS 旅游产品路由：CRUD（A 订制游 + C 权益卡）+ 公开介绍页

公开页 GET /api/v1/cms/products/{slug} 无需登录（供前端 /product/:slug 调用），
仅返回 status=published 的产品。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import Review, TourCustom, TourPass, TourProduct
from ...schemas.cms import (
    ReviewOut,
    TourCustomSchema,
    TourProductCreate,
    TourProductDetail,
    TourProductOut,
    TourProductUpdate,
    TourPassSchema,
)
from ...utils import utcnow

router = APIRouter(prefix="/api/v1/cms/products", tags=["cms-product"])


async def _load_detail(session: AsyncSession, p: TourProduct) -> TourProductDetail:
    """组装产品详情（基本字段 + A/C 扩展）"""
    detail = TourProductDetail.model_validate(p)
    if p.type == "custom":
        c = (
            await session.execute(
                select(TourCustom).where(TourCustom.product_id == p.id)
            )
        ).scalar_one_or_none()
        if c:
            detail.custom = TourCustomSchema.model_validate(c)
    elif p.type == "pass":
        ps = (
            await session.execute(
                select(TourPass).where(TourPass.product_id == p.id)
            )
        ).scalar_one_or_none()
        if ps:
            detail.pass_config = TourPassSchema.model_validate(ps)
    return detail


@router.get("")
async def list_products(
    type: str | None = None,
    status: str | None = None,
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:product:list")),
):
    """产品列表（管理后台，按 type/status/category 过滤）"""
    q = select(TourProduct).order_by(TourProduct.sort, TourProduct.id.desc())
    if type:
        q = q.where(TourProduct.type == type)
    if status:
        q = q.where(TourProduct.status == status)
    if category:
        q = q.where(TourProduct.category == category)
    items = (await session.execute(q)).scalars().all()
    return {"items": [TourProductOut.model_validate(p).model_dump() for p in items]}


@router.get("/{slug}")
async def get_product_by_slug(
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    """公开介绍页（无需登录）：按 slug 查产品详情。

    仅返回 status=published 的产品（草稿/归档不公开）。
    """
    p = (
        await session.execute(select(TourProduct).where(TourProduct.slug == slug))
    ).scalar_one_or_none()
    if not p or p.status != "published":
        raise HTTPException(404, "产品不存在或未发布")
    # 浏览埋点 +1
    p.view_count = (p.view_count or 0) + 1
    await session.commit()
    detail = (await _load_detail(session, p)).model_dump()
    # 附加已审核通过的评论
    reviews = (
        await session.execute(
            select(Review)
            .where(Review.product_id == p.id, Review.status == "approved")
            .order_by(Review.id.desc())
            .limit(20)
        )
    ).scalars().all()
    detail["reviews"] = [ReviewOut.model_validate(r).model_dump() for r in reviews]
    return detail


@router.get("/detail/{product_id}")
async def get_product_detail(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:product:list")),
):
    """管理端详情（含 draft + A/C 扩展，编辑页用）。

    与公开页 /{slug} 区分：此接口需登录 + 权限，返回任意状态产品的完整详情。
    """
    p = await session.get(TourProduct, product_id)
    if not p:
        raise HTTPException(404, "产品不存在")
    return (await _load_detail(session, p)).model_dump()


@router.post("")
async def create_product(
    req: TourProductCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:product:save")),
):
    """创建产品（含 A/C 扩展）"""
    exists = (
        await session.execute(select(TourProduct).where(TourProduct.slug == req.slug))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "slug 已存在")
    data = req.model_dump(exclude={"custom", "pass_config"}, exclude_none=True)
    p = TourProduct(**data)
    if req.status == "published":
        p.published_at = utcnow()
    session.add(p)
    await session.flush()
    if req.type == "custom" and req.custom:
        session.add(TourCustom(product_id=p.id, **req.custom.model_dump()))
    elif req.type == "pass" and req.pass_config:
        session.add(TourPass(product_id=p.id, **req.pass_config.model_dump()))
    await session.commit()
    await session.refresh(p)
    return (await _load_detail(session, p)).model_dump()


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    req: TourProductUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:product:save")),
):
    """更新产品（含扩展 upsert）"""
    p = await session.get(TourProduct, product_id)
    if not p:
        raise HTTPException(404, "产品不存在")
    data = req.model_dump(exclude_unset=True, exclude={"custom", "pass_config"})
    if "slug" in data and data["slug"] != p.slug:
        dup = (
            await session.execute(
                select(TourProduct).where(TourProduct.slug == data["slug"])
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(400, "slug 已存在")
    if data.get("status") == "published" and not p.published_at:
        p.published_at = utcnow()
    for k, v in data.items():
        setattr(p, k, v)
    # 扩展 upsert
    if p.type == "custom" and req.custom is not None:
        c = (
            await session.execute(
                select(TourCustom).where(TourCustom.product_id == p.id)
            )
        ).scalar_one_or_none()
        cdata = req.custom.model_dump()
        if c:
            for k, v in cdata.items():
                setattr(c, k, v)
        else:
            session.add(TourCustom(product_id=p.id, **cdata))
    elif p.type == "pass" and req.pass_config is not None:
        ps = (
            await session.execute(
                select(TourPass).where(TourPass.product_id == p.id)
            )
        ).scalar_one_or_none()
        pdata = req.pass_config.model_dump()
        if ps:
            for k, v in pdata.items():
                setattr(ps, k, v)
        else:
            session.add(TourPass(product_id=p.id, **pdata))
    await session.commit()
    await session.refresh(p)
    return (await _load_detail(session, p)).model_dump()


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:product:save")),
):
    """删除产品（含扩展）"""
    p = await session.get(TourProduct, product_id)
    if not p:
        raise HTTPException(404, "产品不存在")
    for Model in (TourCustom, TourPass):
        ext = (
            await session.execute(
                select(Model).where(Model.product_id == p.id)
            )
        ).scalar_one_or_none()
        if ext:
            await session.delete(ext)
    await session.delete(p)
    await session.commit()
    return {"success": True}
