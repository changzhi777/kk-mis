from .accounts import router as accounts_router
from .categories import router as categories_router
from .reports import router as reports_router
from .transactions import router as transactions_router
from .vouchers import router as vouchers_router

finance_routers = [
    accounts_router,
    categories_router,
    transactions_router,
    reports_router,
    vouchers_router,
]

__all__ = ["finance_routers"]
