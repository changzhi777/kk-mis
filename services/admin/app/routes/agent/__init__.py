from .agents import router as agents_router
from .commissions import router as commissions_router
from .orders import router as orders_router

agent_routers = [
    agents_router,
    orders_router,
    commissions_router,
]

__all__ = ["agent_routers"]
