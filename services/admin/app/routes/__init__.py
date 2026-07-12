from .agent import agent_routers
from .asset import asset_routers
from .audit import router as audit_router
from .auth import router as auth_router
from .auth_oauth import router as auth_oauth_router
from .dashboard import router as dashboard_router
from .oa import oa_routers
from .departments import router as departments_router
from .finance import finance_routers
from .permissions import router as permissions_router
from .roles import router as roles_router
from .users import router as users_router

# 所有路由聚合，main 循环注册
all_routers = [
    auth_router,
    auth_oauth_router,
    dashboard_router,
    users_router,
    roles_router,
    permissions_router,
    departments_router,
    audit_router,
    *finance_routers,
    *asset_routers,
    *agent_routers,
    *oa_routers,
]

__all__ = ["all_routers"]
