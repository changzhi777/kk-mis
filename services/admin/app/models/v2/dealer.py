"""V2.0 经销商域模型（B2B 经销商预付激活模型，2026-07-21）

V2.0 重构：从 B2C 客户付费改为 B2B 经销商预付。客户免费体验，
经销商 C 端化付款给平台（预付充值买名额），平台阶梯返点经销商。

经销商生命周期：申请 → 审核 → 开通 → 后台补资质 → 签合同 → 充值预付 → 运营
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
  + .zcf/plan/current/v2-app-redesign.md
"""
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from ..base import Base
from ..enterprise import pk
from ...utils import utcnow


class V2DealerApplication(Base):
    """经销商申请（准经销商提交 → 超管审批 → 开通经销商身份）。

    申请轻量（user_id + 意向省份），主体资质在开通后于后台分步补充核验。
    """

    __tablename__ = "v2_dealer_application"

    id = pk()
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    province_code = Column(String(16), nullable=False, index=True)  # 意向省份（归属锁定）
    channel_note = Column(String(100), nullable=True)  # 渠道备注
    status = Column(
        String(16), default="pending", nullable=False, index=True
    )  # pending / approved / rejected
    approved_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    reject_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class V2DealerContract(Base):
    """经销商合同（开通后签：服务费模式 / 费率 / 阶梯返点档 / 期限）。

    service_fee_rate / rebate_tiers 具体值待合同阶段定（计划"待定项"），字段占位。
    """

    __tablename__ = "v2_dealer_contract"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    # per_unit（按激活数）/ monthly（月固定）/ wholesale（批发价）— 模式待合同阶段定
    service_fee_mode = Column(String(16), default="per_unit")
    service_fee_rate = Column(Numeric(8, 4), nullable=True)  # 费率（占位，待合同阶段）
    rebate_tiers = Column(Text, nullable=True)  # JSON 阶梯返点档（占位，待合同阶段）
    status = Column(
        String(16), default="draft", nullable=False, index=True
    )  # draft / active / expired / terminated
    signed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class V2DealerBalance(Base):
    """经销商预付余额（充值买名额，激活客户扣减；余额不足不能激活）。

    一经销商一余额（agent_id unique）。
    """

    __tablename__ = "v2_dealer_balance"
    __table_args__ = (UniqueConstraint("agent_id", name="uq_v2_dealer_balance_agent"),)

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    balance = Column(Numeric(12, 2), default=Decimal("0"), nullable=False)  # 当前可用余额
    frozen = Column(Numeric(12, 2), default=Decimal("0"), nullable=False)  # 冻结（激活预占）
    total_recharged = Column(Numeric(12, 2), default=Decimal("0"), nullable=False)  # 累计充值
    total_consumed = Column(Numeric(12, 2), default=Decimal("0"), nullable=False)  # 累计消耗
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class V2DealerRecharge(Base):
    """经销商充值记录（微信/支付宝 C 端 APP 支付 / 银行转账，经销商 C 端化付款）。"""

    __tablename__ = "v2_dealer_recharge"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    channel = Column(String(16), nullable=False)  # wechat / alipay / transfer
    txn_id = Column(String(64), nullable=True, index=True)  # 网关交易号
    status = Column(
        String(16), default="pending", nullable=False, index=True
    )  # pending / paid / failed
    created_at = Column(DateTime, default=utcnow)
    paid_at = Column(DateTime, nullable=True)
    remark = Column(String(200), nullable=True)


class V2DealerQualification(Base):
    """经销商主体资质（M1.5：approve 后后台分步补充 + 平台核验）。

    营业执照/法人/统一社会信用代码；核验状态 pending/verified/rejected。
    """

    __tablename__ = "v2_dealer_qualification"

    id = pk()
    agent_id = Column(BigInteger, ForeignKey("agent.id"), nullable=False, index=True)
    company_name = Column(String(100), nullable=False)  # 企业名称
    legal_person = Column(String(50), nullable=True)  # 法人
    business_license_no = Column(String(32), nullable=True, index=True)  # 统一社会信用代码
    business_license_url = Column(String(255), nullable=True)  # 营业执照图片（COS URL）
    status = Column(
        String(16), default="pending", nullable=False, index=True
    )  # pending / verified / rejected
    verified_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    reject_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
