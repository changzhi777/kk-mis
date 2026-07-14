"""CMS 数据看板统计（admin 聚合）"""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import InquiryLead, ProductOrder, TourProduct
from ...schemas.cms import DashboardStats

router = APIRouter(prefix="/api/v1/cms/stats", tags=["cms-stats"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("cms:product:list")),
):
    """CMS 数据看板：产品/浏览/线索/订单 聚合统计"""
    products_total = (await session.execute(select(func.count(TourProduct.id)))).scalar() or 0
    products_published = (
        await session.execute(
            select(func.count(TourProduct.id)).where(TourProduct.status == "published")
        )
    ).scalar() or 0
    views_total = (
        await session.execute(select(func.coalesce(func.sum(TourProduct.view_count), 0)))
    ).scalar() or 0
    top = (
        await session.execute(
            select(TourProduct.title, TourProduct.slug, TourProduct.view_count)
            .order_by(TourProduct.view_count.desc())
            .limit(5)
        )
    ).all()
    leads_total = (await session.execute(select(func.count(InquiryLead.id)))).scalar() or 0
    leads_new = (
        await session.execute(
            select(func.count(InquiryLead.id)).where(InquiryLead.status == "new")
        )
    ).scalar() or 0
    orders_total = (await session.execute(select(func.count(ProductOrder.id)))).scalar() or 0
    orders_paid = (
        await session.execute(
            select(func.count(ProductOrder.id)).where(ProductOrder.pay_status == "paid")
        )
    ).scalar() or 0
    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(ProductOrder.total), 0)).where(
                ProductOrder.pay_status == "paid"
            )
        )
    ).scalar() or Decimal("0")
    return DashboardStats(
        products_total=products_total,
        products_published=products_published,
        views_total=views_total,
        top_products=[{"title": t, "slug": s, "view_count": v or 0} for t, s, v in top],
        leads_total=leads_total,
        leads_new=leads_new,
        orders_total=orders_total,
        orders_paid=orders_paid,
        revenue=revenue,
    )
