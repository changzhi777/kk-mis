"""V2.0 团期 + 资源库存 + 客户预约（M3.1：预约团期 b-简，房+车 2 维先）

客户激活套餐（授权码 activated）后，预约具体团期出行（选人数 + 房/车资源）。
资源 b-简：M3 先房(hotel)+车(car) 2 维，导游/餐/门票 M4/M5 补。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from ..base import Base
from ..enterprise import pk
from ...utils import utcnow


class V2TourGroup(Base):
    """团期（套餐的具体出发批次，超管发布）。"""

    __tablename__ = "v2_tour_group"

    id = pk()
    product_id = Column(
        BigInteger, ForeignKey("cms_tour_product.id"), nullable=False, index=True
    )
    title = Column(String(100), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    capacity = Column(Integer, nullable=False)  # 人数容量
    booked = Column(Integer, default=0, nullable=False)  # 已预约人数
    status = Column(
        String(16), default="open", nullable=False, index=True
    )  # open / full / closed
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class V2ResourceStock(Base):
    """团期资源库存（b-简：hotel 房 / car 车 2 维先）。"""

    __tablename__ = "v2_resource_stock"
    __table_args__ = (
        UniqueConstraint(
            "tour_group_id", "resource_type", name="uq_v2_resource_group_type"
        ),
    )

    id = pk()
    tour_group_id = Column(
        BigInteger, ForeignKey("v2_tour_group.id"), nullable=False, index=True
    )
    resource_type = Column(String(16), nullable=False)  # hotel / car
    total_qty = Column(Integer, nullable=False)
    used_qty = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class V2Reservation(Base):
    """客户预约（激活套餐后选团期出行）。"""

    __tablename__ = "v2_reservation"

    id = pk()
    customer_user_id = Column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    tour_group_id = Column(
        BigInteger, ForeignKey("v2_tour_group.id"), nullable=False, index=True
    )
    activation_code_id = Column(
        BigInteger, nullable=True, index=True
    )  # 关联授权码（权益来源，可空）
    people_count = Column(Integer, nullable=False)
    hotel_qty = Column(Integer, default=0, nullable=False)
    car_qty = Column(Integer, default=0, nullable=False)
    status = Column(
        String(16), default="confirmed", nullable=False, index=True
    )  # confirmed / cancelled / used
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
