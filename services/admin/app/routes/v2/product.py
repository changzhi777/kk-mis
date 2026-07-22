"""V2.0 套餐路由（M1.6：复用 CMS TourProduct，经销商/客户只读目录）

V2.0 套餐 = 平台供应商发布的旅游产品（**复用 CMS TourProduct，不新建模型**）。
- 平台发布套餐走 CMS `/api/v1/cms/products` CRUD（已存在，零新代码）；
- 经销商/客户经此 v2 端点查看已发布套餐目录（published only）；
- M2 经销商充值预付 + 采购在此目录基础上展开。

详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import TourProduct, User
from ...schemas.cms import TourProductOut

router = APIRouter(prefix="/api/v2/products", tags=["v2-product"])


@router.get("", response_model=list[TourProductOut])
async def list_v2_products(
    type: str | None = None,
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商/客户可见的已发布套餐列表（复用 CMS TourProduct，published only）。

    可选按 type（custom 订制游 / pass 权益卡）/ category 过滤。
    平台发布套餐走 CMS CRUD；此端点供 v2 APP 查看可采购套餐目录。
    """
    q = (
        select(TourProduct)
        .where(TourProduct.status == "published")
        .order_by(TourProduct.sort, TourProduct.id.desc())
    )
    if type:
        q = q.where(TourProduct.type == type)
    if category:
        q = q.where(TourProduct.category == category)
    items = (await session.execute(q)).scalars().all()
    return items
