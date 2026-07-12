"""审计日志模型"""
from ..utils import utcnow
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from .base import Base
from .enterprise import pk


class AuditLog(Base):
    """操作审计日志（中间件自动记录写操作）"""
    __tablename__ = "audit_log"

    id = pk()
    user_id = Column(BigInteger, nullable=True, index=True)
    username = Column(String(50), nullable=True)
    method = Column(String(10), nullable=False)  # POST/PUT/DELETE
    path = Column(String(200), nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    ip = Column(String(50), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)
