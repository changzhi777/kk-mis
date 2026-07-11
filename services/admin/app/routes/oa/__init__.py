from .announcements import router as announcements_router
from .approvals import router as approvals_router
from .leaves import router as leaves_router

oa_routers = [announcements_router, approvals_router, leaves_router]

__all__ = ["oa_routers"]
