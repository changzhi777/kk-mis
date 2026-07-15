"""代理模型：区域代理 / 订单 / 年度返佣（决策 #3 重构：2026-07-13 推翻 3 级）

变更：
- Agent：去掉 level/parent_id 3 级分销结构；改为平级区域代理（region_code）
- AgentOrder：quantity 触发阶梯折扣（pricing.compute_vip_discount）
- YearlyCommissionRecord：新表，按年度累计销售额阶梯自动结算
- CommissionRule：保留 level 字段（兼容旧 commission_records）但不再按 level 配率
"""

from ..utils import utcnow
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String

from .base import Base
from .enterprise import pk


class Agent(Base):
    """区域代理（按 region_code 平级划分销售范围）"""
    __tablename__ = "agent"

    id = pk()
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(50), nullable=True)  # 代理名称
    # 区域代理（替代 3 级分销）
    region_code = Column(String(16), nullable=False, index=True)  # 如 'SH' / 'BJ' / 'GZ'
    region_name = Column(String(64), nullable=True)  # '上海' / '北京' / '广州'
    # 兼容字段：commission_rate 上限 ≤ 0.5（决策 #3 合规边界），用于单次返佣比例
    commission_rate = Column(Numeric(5, 4), default=Decimal("0"))
    promo_code = Column(String(16), unique=True, nullable=True, index=True)  # A1 推广码（8位，create 时生成）
    status = Column(Boolean, default=True)
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AgentOrder(Base):
    """代理订单（区域代理进货卡券批次，按 quantity 自动阶梯折扣）"""
    __tablename__ = "agent_order"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    batch_id = Column(BigInteger, ForeignKey("asset_card_batch.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)  # 折扣后单价
    original_unit_price = Column(Numeric(12, 2), nullable=False)  # 折扣前单价（VIP 1888）
    discount_tier = Column(String(16), nullable=True)  # 折扣档：full / 70 / 60 / 50
    total = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending/paid/completed/cancelled
    region_code = Column(String(16), nullable=True, index=True)  # 冗余存，便于按区域汇总
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # 复合索引：yearly_commission 聚合查询（按 agent_id + 年度范围 + status 过滤）走 B-tree
    # 替代原 func.extract("year", created_at) 全表扫
    __table_args__ = (
        Index(
            "ix_agent_order_agent_created_status",
            "agent_id",
            "created_at",
            "status",
        ),
    )


class CommissionRule(Base):
    """分润规则（决策 #3 推翻后保留为兼容；不再按 level 配率，按年度累计阶梯）"""
    __tablename__ = "commission_rule"

    id = pk()
    level = Column(Integer, nullable=False, unique=True)  # 1 / 2（保留兼容旧数据）
    rate = Column(Numeric(5, 4), nullable=False)  # 0.20 / 0.10（保留兼容）
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class CommissionRecord(Base):
    """单次返佣记录（订单完成时生成，pending→settled）"""
    __tablename__ = "commission_record"

    id = pk()
    order_id = Column(BigInteger, ForeignKey("agent_order.id"), nullable=False, index=True)
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    level = Column(Integer, nullable=True)  # 兼容字段
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending/settled
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ReferralCommission(Base):
    """A2 推荐返佣（C 端 ProductOrder 完成时生成，代理推荐客户返佣 total*5%）"""
    __tablename__ = "referral_commission"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    product_order_id = Column(BigInteger, ForeignKey("cms_product_order.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending/settled/withdrawn
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class WithdrawalRequest(Base):
    """A3 代理提现申请（pending→approved→paid / rejected）"""
    __tablename__ = "withdrawal_request"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending/approved/rejected/paid
    bank_info = Column(String(200), nullable=True)  # 收款信息（银行卡/微信）
    reviewed_by = Column(BigInteger, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class YearlyCommissionRule(Base):
    """年度返佣阶梯规则（按累计销售额分档）"""
    __tablename__ = "yearly_commission_rule"

    id = pk()
    tier = Column(String(16), nullable=False, unique=True)  # 'T1'/'T2'/'T3'
    min_sales = Column(Numeric(14, 2), default=Decimal("0"))  # 累计销售额下限
    max_sales = Column(Numeric(14, 2), nullable=True)  # 累计销售额上限（NULL = 无限）
    commission_pct = Column(Numeric(5, 4), nullable=False)  # 0.30 / 0.40 / 0.50
    sort = Column(Integer, default=0)  # 升序
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class YearlyCommissionRecord(Base):
    """年度返佣结算记录（按自然年，每个 agent 一条）"""
    __tablename__ = "yearly_commission_record"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)  # 自然年（YYYY）
    total_sales = Column(Numeric(14, 2), default=Decimal("0"))  # 该年累计销售额
    tier = Column(String(16), nullable=True)  # 命中的阶梯（T1/T2/T3）
    commission_pct = Column(Numeric(5, 4), default=Decimal("0"))  # 命中的返佣比例
    amount = Column(Numeric(14, 2), default=Decimal("0"))  # 结算金额 = total_sales × pct
    order_count = Column(Integer, default=0)  # 该年订单数（冗余）
    payout_status = Column(String(20), default="pending")  # pending/settled/cancelled
    settled_at = Column(DateTime, nullable=True)
    region_code = Column(String(16), nullable=True, index=True)  # 冗余存，便于按区域汇总
    created_at = Column(DateTime, default=utcnow)
