"""SQLAlchemy 数据库模型"""
from datetime import datetime
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Meeting(Base):
    """会议表"""

    __tablename__ = "meetings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 基本信息
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    meeting_date = Column(DateTime, nullable=True, index=True)

    # 状态
    status = Column(String(32), nullable=False, default="uploaded", index=True)

    # 音频信息
    audio_filename = Column(String(255), nullable=True)
    audio_path = Column(String(512), nullable=True)
    audio_size_bytes = Column(BigInteger, nullable=True)
    audio_duration = Column(Float, nullable=True)
    language = Column(String(16), nullable=True, default="zh")

    # ASR 结果
    raw_transcript = Column(Text, nullable=True)
    segments = Column(JSON, nullable=True)  # List[Segment]
    asr_model = Column(String(128), nullable=True)
    asr_node_id = Column(String(64), nullable=True)

    # LLM 整理结果
    summary = Column(Text, nullable=True)
    key_points = Column(JSON, nullable=True)  # List[str]
    decisions = Column(JSON, nullable=True)  # List[str]
    action_items = Column(JSON, nullable=True)  # List[ActionItem]
    llm_model = Column(String(128), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "meeting_date": self.meeting_date.isoformat() if self.meeting_date else None,
            "status": self.status,
            "duration": self.audio_duration,
            "raw_transcript": self.raw_transcript,
            "segments": self.segments,
            "summary": self.summary,
            "key_points": self.key_points,
            "decisions": self.decisions,
            "action_items": self.action_items,
            "audio_filename": self.audio_filename,
            "asr_model": self.asr_model,
            "asr_node_id": self.asr_node_id,
            "llm_model": self.llm_model,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }