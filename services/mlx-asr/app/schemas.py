"""Pydantic 数据模型"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Segment(BaseModel):
    """单个转写片段"""

    id: int = Field(..., description="片段序号")
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    text: str = Field(..., description="片段文本")
    speaker: Optional[str] = Field(None, description="说话人标签")


class TranscriptionResult(BaseModel):
    """转写结果"""

    text: str = Field(..., description="完整文本")
    language: str = Field(..., description="识别语言")
    duration: float = Field(..., description="音频时长（秒）")
    model: str = Field(..., description="使用的模型")
    segments: List[Segment] = Field(default_factory=list, description="分段详情")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "今天我们讨论一下 V2.0 的需求优先级",
                "language": "zh",
                "duration": 60.5,
                "model": "mlx-community/whisper-large-v3-turbo",
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 5.2,
                        "text": "今天我们讨论一下 V2.0 的需求优先级",
                        "speaker": None,
                    }
                ],
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    model: str
    cache_dir: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str
    detail: Optional[str] = None