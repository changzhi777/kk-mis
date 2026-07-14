from .coupons import router as coupons_router
from .leads import router as leads_router
from .media import router as media_router
from .merchants import router as merchants_router
from .orders import router as orders_router
from .products import router as products_router

cms_routers = [products_router, media_router, merchants_router, leads_router, orders_router, coupons_router]

__all__ = ["cms_routers"]
