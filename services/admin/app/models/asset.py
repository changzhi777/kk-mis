"""资产模型：卡券类型/批次/卡券实例/核销记录"""
from ..utils import utcnow
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from .base import Base
from .enterprise import pk


class AssetCardType(Base):
    """卡券类型（VIP卡/代金券/兑换券/储值卡）"""
    __tablename__ = "asset_card_type"

    id = pk()
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)  # vip/voucher/exchange/stored
    face_value = Column(Numeric(12, 2), default=Decimal("0"))  # 面值（代金券/储值卡）
    valid_days = Column(Integer, default=0)  # 有效期天数（VIP卡）
    fields_config = Column(String(500), nullable=True)  # JSON 自定义字段
    status = Column(Boolean, default=True)
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AssetCardBatch(Base):
    """卡券批次"""
    __tablename__ = "asset_card_batch"

    id = pk()
    type_id = Column(BigInteger, ForeignKey("asset_card_type.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    quantity = Column(Integer, default=0)  # 计划数量
    generated = Column(Integer, default=0)  # 已生成
    status = Column(String(20), default="draft")  # draft/active/closed
    valid_until = Column(DateTime, nullable=True)  # 批次有效期
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AssetCard(Base):
    """卡券实例"""
    __tablename__ = "asset_card"
    # 状态机：draft(待发放)→issued(已发放)→used(已核销)→(refunded/expired/void)

    id = pk()
    batch_id = Column(BigInteger, ForeignKey("asset_card_batch.id"), nullable=False, index=True)
    type_id = Column(BigInteger, ForeignKey("asset_card_type.id"), nullable=False, index=True)
    card_no = Column(String(32), unique=True, nullable=False, index=True)  # 16位卡号
    password_hash = Column(String(255), nullable=False)  # 6位密码哈希
    status = Column(String(20), default="draft", nullable=False, index=True)
    face_value = Column(Numeric(12, 2), default=Decimal("0"))
    holder_user_id = Column(BigInteger, nullable=True, index=True)
    issued_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AssetRedemption(Base):
    """核销记录"""
    __tablename__ = "asset_redemption"

    id = pk()
    card_id = Column(BigInteger, ForeignKey("asset_card.id"), nullable=False, index=True)
    redeemer_id = Column(BigInteger, nullable=True)  # 核销人 user_id
    method = Column(String(20), nullable=False)  # scan/manual/batch/self
    amount = Column(Numeric(12, 2), default=Decimal("0"))
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)
