"""代理 Schema：代理/订单/分润规则/分润记录"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ===== 代理 =====
class AgentCreate(BaseModel):
    user_id: int
    name: Optional[str] = None
    level: int = Field(1, ge=1, le=2)
    parent_id: Optional[int] = None
    commission_rate: Decimal = Decimal("0")
    status: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = Field(None, ge=1, le=2)
    parent_id: Optional[int] = None
    commission_rate: Optional[Decimal] = None
    status: Optional[bool] = None


class AgentOut(BaseModel):
    id: int
    user_id: int
    name: Optional[str] = None
    level: int
    parent_id: Optional[int] = None
    commission_rate: Decimal
    status: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===== 订单 =====
class OrderCreate(BaseModel):
    agent_id: int
    batch_id: int
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    remark: Optional[str] = None


class OrderOut(BaseModel):
    id: int
    agent_id: int
    batch_id: int
    quantity: int
    unit_price: Decimal
    total: Decimal
    status: str
    remark: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== 分润规则 =====
class CommissionRuleCreate(BaseModel):
    level: int = Field(..., ge=1, le=2)
    rate: Decimal = Field(..., ge=0, le=1)
    status: bool = True


class CommissionRuleOut(CommissionRuleCreate):
    id: int

    class Config:
        from_attributes = True


# ===== 分润记录 =====
class CommissionRecordOut(BaseModel):
    id: int
    order_id: int
    agent_id: int
    level: int
    amount: Decimal
    status: str
    settled_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
