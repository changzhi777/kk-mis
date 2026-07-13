"""财务 Schema：账户/科目/流水"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===== 账户 =====
class AccountCreate(BaseModel):
    name: str = Field(..., max_length=50)
    type: str = Field(..., pattern="^(cash|bank|wechat|alipay|other)$")
    balance: Decimal = Decimal("0")
    sort: int = 0
    status: bool = True


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[bool] = None


class AccountOut(BaseModel):
    id: int
    name: str
    type: str
    balance: Decimal
    sort: int
    status: bool

    model_config = ConfigDict(from_attributes=True)


# ===== 科目 =====
class CategoryCreate(BaseModel):
    parent_id: Optional[int] = None
    name: str = Field(..., max_length=50)
    type: str = Field(..., pattern="^(income|expense)$")
    code: Optional[str] = None
    sort: int = 0
    status: bool = True


class CategoryUpdate(CategoryCreate):
    pass


class CategoryOut(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    type: str
    code: Optional[str] = None
    sort: int
    status: bool

    model_config = ConfigDict(from_attributes=True)


# ===== 流水 =====
class TransactionCreate(BaseModel):
    type: str = Field(..., pattern="^(income|expense)$")
    amount: Decimal = Field(..., gt=0)
    account_id: int
    category_id: int
    dept_id: Optional[int] = None
    transaction_date: datetime
    remark: Optional[str] = Field(None, max_length=500)


class TransactionOut(BaseModel):
    id: int
    type: str
    amount: Decimal
    account_id: int
    category_id: int
    dept_id: Optional[int] = None
    user_id: Optional[int] = None
    transaction_date: datetime
    remark: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
