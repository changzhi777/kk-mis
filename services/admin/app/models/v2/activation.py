"""V2.0 授权码模型（客户→经销商扫码激活付费，M2.1/2.2）

与推广码（Agent.promo_code，经销商→客户扫，锁定归属）分离：
- 推广码 = 归属锁定（agent_id + province 终身），客户扫推广码注册时锁定经销商；
- 授权码 = 激活付费，客户主动生成（5-10min 时效 + 一次性），经销商扫码发起激活，
  客户二次确认后扣经销商预付余额 + 套餐生效。

授权码 4 项安全（防经销商强制激活）：客户主动生成 + 时效 5-10min + 一次性 + 客户二次确认。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
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


class V2ActivationCode(Base):
    """客户授权码（激活付费凭证）。

    生命周期：pending(客户生成) → activating(经销商发起,冻结余额) → activated(客户确认,扣款)
              / expired(超时) / cancelled。
    agent_id 生成时锁定（客户扫推广码归属），经销商扫码激活不需再确认归属。
    """

    __tablename__ = "v2_activation_code"
    __table_args__ = (UniqueConstraint("code", name="uq_v2_activation_code"),)

    id = pk()
    code = Column(String(16), nullable=False, index=True)  # 6-8 位
    customer_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    # 归属经销商（客户扫推广码锁定，激活时不需再确认）
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    product_id = Column(BigInteger, ForeignKey("cms_tour_product.id"), nullable=False)  # 套餐
    price = Column(Numeric(12, 2), nullable=False)  # 经销商扣款金额（套餐服务费）
    status = Column(
        String(16), default="pending", nullable=False, index=True
    )  # pending/activating/activated/expired/cancelled
    expires_at = Column(DateTime, nullable=False)  # 5-10min 时效
    initiated_at = Column(DateTime, nullable=True)  # 经销商发起激活时间
    activated_at = Column(DateTime, nullable=True)  # 客户确认时间
    created_at = Column(DateTime, default=utcnow)
