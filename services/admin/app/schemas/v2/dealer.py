"""V2.0 经销商 schema（申请 + 合同，M1.2/M1.4）"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ===== 经销商申请（M1.2）=====
class V2DealerApplicationCreate(BaseModel):
    province_code: str = Field(..., max_length=16)  # 意向省份（归属锁定）
    channel_note: Optional[str] = Field(None, max_length=100)


class V2DealerApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    province_code: str
    channel_note: Optional[str]
    status: str
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    reject_reason: Optional[str]
    created_at: Optional[datetime]


class V2DealerApplicationReject(BaseModel):
    reason: str = Field(..., max_length=200)


# ===== 经销商合同（M1.4）=====
class V2DealerContractCreate(BaseModel):
    agent_id: int
    start_date: datetime
    end_date: datetime
    # per_unit（按激活数）/ monthly（月固定）/ wholesale（批发价）— 模式待合同阶段
    service_fee_mode: str = "per_unit"
    service_fee_rate: Optional[Decimal] = None  # 费率（占位，待合同阶段）
    rebate_tiers: Optional[str] = None  # JSON 阶梯返点档（占位，待合同阶段）


class V2DealerContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    start_date: datetime
    end_date: datetime
    service_fee_mode: str
    service_fee_rate: Optional[Decimal]
    rebate_tiers: Optional[str]
    status: str
    signed_at: Optional[datetime]
    created_at: Optional[datetime]
