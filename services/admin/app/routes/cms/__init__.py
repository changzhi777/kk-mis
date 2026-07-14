from .coupons import router as coupons_router
from .leads import router as leads_router
from .media import router as media_router
from .merchants import router as merchants_router
from .orders import router as orders_router
from .payments import router as payments_router
from .products import router as products_router
from .reviews import router as reviews_router
from .stats import router as stats_router

cms_routers = [
    products_router,
    media_router,
    merchants_router,
    leads_router,
    orders_router,
    coupons_router,
    reviews_router,
    stats_router,
    payments_router,
]

__all__ = ["cms_routers"]
