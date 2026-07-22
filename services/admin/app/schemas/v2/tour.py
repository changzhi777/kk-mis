"""V2.0 团期 + 预约 schema（M3.1）"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class V2TourGroupCreate(BaseModel):
    """超管发布团期（含房+车资源库存）。"""

    product_id: int
    title: str = Field(..., max_length=100)
    start_date: datetime
    end_date: datetime
    capacity: int = Field(..., gt=0)
    hotel_qty: int = Field(0, ge=0)
    car_qty: int = Field(0, ge=0)


class V2ResourceStockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resource_type: str
    total_qty: int
    used_qty: int


class V2TourGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    title: str
    start_date: datetime
    end_date: datetime
    capacity: int
    booked: int
    status: str
    resources: list[V2ResourceStockOut] = []


class V2ReservationCreate(BaseModel):
    """客户预约（选团期 + 人数 + 房/车）。"""

    tour_group_id: int
    activation_code_id: Optional[int] = None  # 关联授权码（权益来源）
    people_count: int = Field(..., gt=0)
    hotel_qty: int = Field(0, ge=0)
    car_qty: int = Field(0, ge=0)


class V2ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_user_id: int
    tour_group_id: int
    activation_code_id: Optional[int]
    people_count: int
    hotel_qty: int
    car_qty: int
    status: str
    created_at: Optional[datetime]
