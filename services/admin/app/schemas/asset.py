"""资产 Schema：卡券类型/批次/卡券/核销"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ===== 卡券类型 =====
class CardTypeBase(BaseModel):
    name: str = Field(..., max_length=50)
    type: str = Field(..., pattern="^(vip|voucher|exchange|stored)$")
    face_value: Decimal = Decimal("0")
    valid_days: int = 0
    fields_config: Optional[str] = None
    status: bool = True
    remark: Optional[str] = None


class CardTypeCreate(CardTypeBase):
    pass


class CardTypeUpdate(CardTypeBase):
    pass


class CardTypeOut(CardTypeBase):
    id: int

    class Config:
        from_attributes = True


# ===== 批次 =====
class BatchCreate(BaseModel):
    type_id: int
    name: str = Field(..., max_length=100)
    quantity: int = Field(..., gt=0)
    valid_until: Optional[datetime] = None


class BatchOut(BaseModel):
    id: int
    type_id: int
    name: str
    quantity: int
    generated: int
    status: str
    valid_until: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateCardsRequest(BaseModel):
    quantity: int = Field(..., gt=0, le=10000)


class GeneratedCard(BaseModel):
    """生成卡券的明文返回（一次性，用于导出/打印）"""
    card_no: str
    password: str


# ===== 卡券 =====
class CardOut(BaseModel):
    id: int
    batch_id: int
    type_id: int
    card_no: str
    status: str
    face_value: Decimal
    holder_user_id: Optional[int] = None
    issued_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IssueRequest(BaseModel):
    holder_user_id: int


# ===== 核销 =====
class RedemptionRequest(BaseModel):
    card_no: str
    password: Optional[str] = None  # self 自助核销需密码
    method: str = Field("scan", pattern="^(scan|manual|batch|self)$")
    remark: Optional[str] = None


class RedemptionOut(BaseModel):
    id: int
    card_id: int
    redeemer_id: Optional[int] = None
    method: str
    amount: Decimal
    remark: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
