"""V2.0 商业 schema（推广码 + 充值 + 余额，M2.1/2.3）"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class V2PromoCodeOut(BaseModel):
    """经销商推广码（复用 Agent.promo_code）。"""

    promo_code: str
    agent_id: int


class V2RechargeCreate(BaseModel):
    """经销商充值（M2.3 mock 网关立即确认；M2.5 接微信/支付宝真支付）。"""

    amount: Decimal = Field(..., gt=0)  # 充值金额（元）
    channel: str = Field("mock", max_length=16)  # mock / wechat / alipay / transfer


class V2RechargeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    amount: Decimal
    channel: str
    txn_id: Optional[str]
    status: str
    created_at: Optional[datetime]
    paid_at: Optional[datetime]
    remark: Optional[str]


class V2BalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: int
    balance: Decimal
    frozen: Decimal
    total_recharged: Decimal
    total_consumed: Decimal


class V2DashboardOut(BaseModel):
    """经销商工作台聚合（M3.5：余额/激活/返点 概览）。"""

    balance: Decimal
    frozen: Decimal
    total_recharged: Decimal
    total_consumed: Decimal
    activated_count: int  # 已激活（未退款）授权码数
    total_rebate: Decimal  # 累计已结算返点
