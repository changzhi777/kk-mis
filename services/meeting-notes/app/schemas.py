"""Pydantic 数据模型 - API 请求/响应"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MeetingStatus(str, Enum):
    """会议处理状态"""

    UPLOADED = "uploaded"  # 音频已上传
    TRANSCRIBING = "transcribing"  # ASR 处理中
    TRANSCRIBED = "transcribed"  # ASR 完成
    SUMMARIZING = "summarizing"  # LLM 整理中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败


class ActionItem(BaseModel):
    """行动项"""

    id: Optional[int] = None
    task: str = Field(..., description="任务描述")
    owner: Optional[str] = Field(None, description="负责人")
    deadline: Optional[str] = Field(None, description="截止日期")
    priority: Optional[str] = Field(None, description="优先级 P0/P1/P2")
    status: str = Field(default="pending", description="状态")


class Segment(BaseModel):
    """转写片段"""

    id: int
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


class MeetingCreate(BaseModel):
    """创建会议请求"""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    language: str = Field(default="zh", description="音频语言")


class MeetingResponse(BaseModel):
    """会议响应"""

    id: int
    title: str
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    duration: Optional[float] = None
    status: MeetingStatus

    # 原始转写
    raw_transcript: Optional[str] = None
    segments: Optional[List[Segment]] = None

    # LLM 整理后的纪要
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    decisions: Optional[List[str]] = None
    action_items: Optional[List[ActionItem]] = None

    # 元数据
    audio_filename: Optional[str] = None
    asr_model: Optional[str] = None
    llm_model: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MeetingListResponse(BaseModel):
    """会议列表响应"""

    total: int
    items: List[MeetingResponse]
    page: int = 1
    page_size: int = 20


class UploadResponse(BaseModel):
    """上传响应"""

    meeting_id: int
    filename: str
    size_mb: float
    status: MeetingStatus
    message: str = "音频已上传，转写任务已启动"


class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str
    meeting_id: int
    status: MeetingStatus
    progress: int = 0  # 0-100
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查"""

    status: str
    version: str
    asr_nodes: int
    llm_provider: str
    database: str