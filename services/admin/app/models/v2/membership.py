"""V2.0 客户权益（M3.2：激活 confirm 后建，核销后 used）

客户扫授权码激活套餐 → 经销商扣款 + 客户获权益（V2Membership active）→
预约团期出行核销 → membership used。
替代 V1 product_order 的客户支付字段（V2.0 客户不付款，权益来自经销商激活）。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String

from ..base import Base
from ..enterprise import pk
from ...utils import utcnow


class V2Membership(Base):
    """客户套餐权益（来源：授权码激活；状态：active → used / expired）。"""

    __tablename__ = "v2_membership"

    id = pk()
    customer_user_id = Column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    activation_code_id = Column(BigInteger, nullable=False, index=True)  # 来源授权码
    product_id = Column(
        BigInteger, ForeignKey("cms_tour_product.id"), nullable=False
    )
    status = Column(
        String(16), default="active", nullable=False, index=True
    )  # active / used / expired
    activated_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    reservation_id = Column(BigInteger, nullable=True)  # 核销时关联预约
    created_at = Column(DateTime, default=utcnow)
