"""OA Schema：公告 + 审批 + 请假"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ===== 公告 =====
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


# ===== 审批流程定义 =====
class ApprovalFlowCreate(BaseModel):
    name: str = Field(..., max_length=100)
    business_type: str = Field(..., pattern="^(leave|expense)$")
    nodes_config: str  # JSON 字符串
    status: bool = True


class ApprovalFlowOut(ApprovalFlowCreate):
    id: int

    class Config:
        from_attributes = True


# ===== 审批实例/记录 =====
class ApprovalInstanceOut(BaseModel):
    id: int
    flow_id: int
    applicant_id: int
    business_type: str
    business_id: int
    status: str
    current_node: int
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovalRecordOut(BaseModel):
    id: int
    instance_id: int
    node: int
    approver_id: int
    action: str
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=500)


# ===== 请假 =====
class LeaveCreate(BaseModel):
    type: str = Field(..., pattern="^(personal|sick|annual)$")
    start_date: datetime
    end_date: datetime
    days: Decimal = Field(..., gt=0, le=365)
    reason: Optional[str] = Field(None, max_length=500)


class LeaveOut(BaseModel):
    id: int
    user_id: int
    type: str
    start_date: datetime
    end_date: datetime
    days: Decimal
    reason: Optional[str] = None
    status: str
    instance_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
