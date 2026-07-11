"""OA 办公模型：公告"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String, Text

from .base import Base
from .enterprise import pk


class Announcement(Base):
    """公告/通知（scope: all 全员 / dept 指定部门）"""
    __tablename__ = "announcement"

    id = pk()
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    publisher_id = Column(BigInteger, nullable=True)
    scope = Column(String(20), default="all")  # all / dept
    dept_id = Column(BigInteger, nullable=True)
    status = Column(String(20), default="draft", nullable=False, index=True)  # draft/published/archived
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
