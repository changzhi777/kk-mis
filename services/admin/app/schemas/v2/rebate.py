"""V2.0 返点 schema（M2.4 月结）"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class V2RebateRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    period: str
    total_sales: Decimal
    tier: Optional[str]
    rebate_pct: Decimal
    rebate_amount: Decimal
    status: str
    settled_at: Optional[datetime]
    created_at: Optional[datetime]


class V2RebateSettle(BaseModel):
    """触发月结（不传 year/month 默认当月）。"""

    year: Optional[int] = Field(None, ge=2000, le=2100)
    month: Optional[int] = Field(None, ge=1, le=12)
