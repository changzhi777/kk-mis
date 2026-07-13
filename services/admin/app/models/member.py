"""会员体系：积分 + 等级（V2 积分 / V3 等级，2026-07-13 深度升级）"""
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from .base import Base
from .enterprise import pk
from ..utils import utcnow


class MemberLevel(Base):
    """会员等级定义（V3）"""
    __tablename__ = "member_level"
    id = pk()
    name = Column(String(32), nullable=False)  # 普通/银/金/钻
    min_consumed = Column(Numeric(14, 2), default=0)  # 升级门槛（累计消费）
    discount = Column(Numeric(3, 2), default=Decimal("1"))  # 折扣 1=原价 0.9=9折
    sort = Column(Integer, default=0)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class MemberStat(Base):
    """会员档案（V2 积分 + V3 等级，按 user 唯一）"""
    __tablename__ = "member_stat"
    id = pk()
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    level_id = Column(BigInteger, ForeignKey("member_level.id"), nullable=True)
    points_balance = Column(Integer, default=0)
    frozen_points = Column(Integer, default=0)
    total_consumed = Column(Numeric(14, 2), default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class PointsLog(Base):
    """积分流水（V2）"""
    __tablename__ = "points_log"
    id = pk()
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    delta = Column(Integer, nullable=False)  # +/- 变动
    balance_after = Column(Integer, nullable=False)  # 变动后余额（审计）
    reason = Column(String(64), nullable=False)  # redeem/award/adjust/exchange
    ref_type = Column(String(32), nullable=True)  # card/order/admin
    ref_id = Column(BigInteger, nullable=True)
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
