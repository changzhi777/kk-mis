"""V2.0 授权码 schema（M2.1/2.2 激活流）"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class V2ActivationCodeCreate(BaseModel):
    """客户生成授权码：扫经销商推广码（锁定归属）+ 选套餐。"""

    promo_code: str = Field(..., max_length=16)  # 经销商推广码
    product_id: int  # 套餐（TourProduct）


class V2ActivationCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    customer_user_id: int
    agent_id: int
    product_id: int
    price: Decimal
    status: str
    expires_at: datetime
    initiated_at: Optional[datetime]
    activated_at: Optional[datetime]
    created_at: Optional[datetime]
