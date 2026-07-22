"""V2.0 业务路由聚合（注册到 /admin/api/v2/*，与 kk-mis /api/v1 隔离）"""
from . import (
    activation,
    dashboard,
    dealer,
    product,
    promo,
    realname,
    rebate,
    recharge,
    tour,
)

v2_routers = [
    dealer.router,
    product.router,
    promo.router,
    recharge.router,
    activation.router,
    realname.router,
    rebate.router,
    tour.router,
    dashboard.router,
]

__all__ = ["v2_routers"]
