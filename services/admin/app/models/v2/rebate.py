"""V2.0 经销商阶梯返点记录（M2.4：月结，返经销商预付余额）

月结模型：每月汇总经销商当月 activated 授权码消费额（total_sales）→ 按阶梯算返点 →
返点金额入经销商余额账户。一个经销商一个月份一条（unique agent_id+period）。
阶梯档：默认 R1/R2/R3（0-1万5% / 1-5万10% / 5万+15%）；合同 rebate_tiers 有值时用合同档（M2.4 先默认）。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)

from ..base import Base
from ..enterprise import pk
from ...utils import utcnow


class V2RebateRecord(Base):
    """经销商月度返点结算记录。"""

    __tablename__ = "v2_rebate_record"
    __table_args__ = (
        UniqueConstraint("agent_id", "period", name="uq_v2_rebate_agent_period"),
    )

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)  # "YYYY-MM"
    total_sales = Column(Numeric(14, 2), default=Decimal("0"))  # 当月激活消费额
    tier = Column(String(16), nullable=True)  # 命中阶梯 R1/R2/R3
    rebate_pct = Column(Numeric(5, 4), default=Decimal("0"))  # 返点比例
    rebate_amount = Column(Numeric(14, 2), default=Decimal("0"))  # 返点金额
    status = Column(
        String(16), default="pending", nullable=False, index=True
    )  # pending / settled
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
