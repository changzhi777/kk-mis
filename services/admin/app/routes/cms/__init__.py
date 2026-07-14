from .media import router as media_router
from .merchants import router as merchants_router
from .products import router as products_router

cms_routers = [products_router, media_router, merchants_router]

__all__ = ["cms_routers"]
