from .agent import agent_routers
from .v2 import v2_routers  # V2.0 业务路由（B2B 经销商预付激活，2026-07-21）
from .asset import asset_routers
from .cms import cms_routers
from .audit import router as audit_router
from .auth import router as auth_router
from .auth_oauth import router as auth_oauth_router
from .dashboard import router as dashboard_router
from .member import router as member_router
from .oa import oa_routers
from .departments import router as departments_router
from .finance import finance_routers
from .oa_agent_bridge import router as oa_agent_bridge_router
from .office import router as office_router
from .tripgen import router as tripgen_router
from .permissions import router as permissions_router
from .roles import router as roles_router
from .storage import router as storage_router
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
    *cms_routers,
    *oa_routers,
    member_router,
    oa_agent_bridge_router,
    office_router,
    tripgen_router,
    storage_router,
    *v2_routers,
]

__all__ = ["all_routers"]
