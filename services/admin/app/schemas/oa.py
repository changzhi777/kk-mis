"""OA Schema：公告"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=200)
    content: str = Field(..., min_length=1)
    scope: str = Field("all", pattern="^(all|dept)$")
    dept_id: Optional[int] = None
    status: str = Field("draft", pattern="^(draft|published)$")


class AnnouncementOut(BaseModel):
    id: int
    title: str
    content: str
    publisher_id: Optional[int] = None
    scope: str
    dept_id: Optional[int] = None
    status: str
    created_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True
