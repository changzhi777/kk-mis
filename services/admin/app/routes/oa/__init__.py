from .announcements import router as announcements_router
from .approvals import router as approvals_router
from .attendance import router as attendance_router
from .expenses import router as expenses_router
from .leaves import router as leaves_router
from .reports import router as reports_router

oa_routers = [
    announcements_router,
    approvals_router,
    leaves_router,
    expenses_router,
    reports_router,
    attendance_router,
]

__all__ = ["oa_routers"]
