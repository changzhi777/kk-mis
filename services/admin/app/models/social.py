"""第三方账号绑定模型（OAuth 登录）"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint

from ..utils import utcnow
from .base import Base
from .enterprise import pk


class SocialAccount(Base):
    """用户绑定的第三方账号（GitHub / 微信等，一人可绑多个）"""
    __tablename__ = "social_account"
    __table_args__ = (
        UniqueConstraint("provider", "provider_uid", name="uq_social_provider_uid"),
    )

    id = pk()
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)  # github / wechat
    provider_uid = Column(String(100), nullable=False)  # 第三方用户唯一ID
    provider_name = Column(String(100), nullable=True)  # 第三方昵称（展示用）
    created_at = Column(DateTime, default=utcnow)
