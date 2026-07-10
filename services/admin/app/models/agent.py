"""代理模型：代理/订单/分润规则/分润记录（3级分销记账）"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from .base import Base
from .enterprise import pk


class Agent(Base):
    """代理（3级树：level 1/2，parent_id 自引用）"""
    __tablename__ = "agent"

    id = pk()
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(50), nullable=True)  # 代理名称（可不同于 user.name）
    level = Column(Integer, nullable=False, default=1)  # 1 一级 / 2 二级
    parent_id = Column(BigInteger, nullable=True, index=True)  # 上级代理 id（自引用）
    commission_rate = Column(Numeric(5, 4), default=Decimal("0"))  # 个人分润率（0.2=20%）
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentOrder(Base):
    """代理订单（进货卡券批次）"""
    __tablename__ = "agent_order"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    batch_id = Column(BigInteger, ForeignKey("asset_card_batch.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending/paid/completed/cancelled
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommissionRule(Base):
    """分润规则（按级别配率：一级 20% / 二级 10%）"""
    __tablename__ = "commission_rule"

    id = pk()
    level = Column(Integer, nullable=False, unique=True)  # 1 / 2
    rate = Column(Numeric(5, 4), nullable=False)  # 0.20 / 0.10
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommissionRecord(Base):
    """分润记录（订单完成时生成，pending→settled）"""
    __tablename__ = "commission_record"

    id = pk()
    order_id = Column(BigInteger, ForeignKey("agent_order.id"), nullable=False, index=True)
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    level = Column(Integer, nullable=False)  # 该代理在该订单中的级别
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending/settled
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
