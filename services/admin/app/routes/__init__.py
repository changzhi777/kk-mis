from .agent import agent_routers
from .asset import asset_routers
from .auth import router as auth_router
from .departments import router as departments_router
from .finance import finance_routers
from .permissions import router as permissions_router
from .roles import router as roles_router
from .users import router as users_router

# 所有路由聚合，main 循环注册
all_routers = [
    auth_router,
    users_router,
    roles_router,
    permissions_router,
    departments_router,
    *finance_routers,
    *asset_routers,
    *agent_routers,
]

__all__ = ["all_routers"]
