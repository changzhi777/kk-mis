"""代理 Schema：区域代理 / 订单 / 分润规则 / 年度返佣（决策 #3 重构：2026-07-13）

合规边界（决策 #3 保留）：
- commission_rate / rate 上限 0.5（50%），防全额返利
- 决策依据：销售返利比例 < 50%（避免被认定为传销）

变更（推翻原 3 级分销）：
- 去掉 level / parent_id 字段
- 加 region_code / region_name（区域代理标识）
- 新增 YearlyCommissionRule / YearlyCommissionRecord / OrderTier 字段
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# 决策 #3 合规上限：从 services.pricing 单一源导入，避免多份漂移
from ..services.pricing import MAX_COMMISSION_RATE


# ===== 代理（区域代理）=====
class AgentCreate(BaseModel):
    user_id: int
    name: Optional[str] = None
    region_code: str = Field(..., min_length=2, max_length=16, description="区域代码，如 'SH'/'BJ'")
    region_name: Optional[str] = Field(None, max_length=64, description="区域名称，如 '上海'")
    commission_rate: Decimal = Field(
        Decimal("0"),
        ge=0,
        le=MAX_COMMISSION_RATE,
        description="单次返佣比例上限 50%（决策 #3 防全额返利）",
    )
    status: bool = True
    remark: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    region_code: Optional[str] = Field(None, min_length=2, max_length=16)
    region_name: Optional[str] = Field(None, max_length=64)
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=MAX_COMMISSION_RATE)
    status: Optional[bool] = None
    remark: Optional[str] = None


class AgentOut(BaseModel):
    id: int
    user_id: int
    name: Optional[str] = None
    region_code: str
    region_name: Optional[str] = None
    commission_rate: Decimal
    status: bool
    remark: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== 订单（区域代理进货）=====
class OrderCreate(BaseModel):
    agent_id: int
    batch_id: int
    quantity: int = Field(..., gt=0, description="进货数量（≥1）")
    remark: Optional[str] = None


class OrderOut(BaseModel):
    id: int
    agent_id: int
    batch_id: int
    quantity: int
    unit_price: Decimal
    original_unit_price: Decimal
    discount_tier: Optional[str] = None
    total: Decimal
    status: str
    region_code: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== 分润规则（兼容旧数据，新逻辑走 YearlyCommissionRule）=====
class CommissionRuleCreate(BaseModel):
    level: int = Field(..., ge=1, le=2)
    rate: Decimal = Field(
        ...,
        ge=0,
        le=MAX_COMMISSION_RATE,
        description="兼容字段，上限 50%（决策 #3 防全额返利）",
    )
    status: bool = True


class CommissionRuleOut(CommissionRuleCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ===== 分润记录 =====
class CommissionRecordOut(BaseModel):
    id: int
    order_id: int
    agent_id: int
    level: Optional[int] = None
    amount: Decimal
    status: str
    settled_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== 年度返佣规则（新增）=====
class YearlyCommissionRuleCreate(BaseModel):
    tier: str = Field(..., min_length=1, max_length=16, description="阶梯 T1/T2/T3")
    min_sales: Decimal = Field(Decimal("0"), ge=0, description="累计销售额下限")
    max_sales: Optional[Decimal] = Field(None, ge=0, description="上限（NULL=无限）")
    commission_pct: Decimal = Field(..., ge=0, le=MAX_COMMISSION_RATE)
    sort: int = 0
    status: bool = True


class YearlyCommissionRuleOut(YearlyCommissionRuleCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== 年度返佣记录（新增）=====
class YearlyCommissionRecordOut(BaseModel):
    id: int
    agent_id: int
    year: int
    total_sales: Decimal
    tier: Optional[str] = None
    commission_pct: Decimal
    amount: Decimal
    order_count: int
    payout_status: str
    settled_at: Optional[datetime] = None
    region_code: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)