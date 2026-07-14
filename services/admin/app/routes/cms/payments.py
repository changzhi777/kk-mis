"""支付回调路由（网关异步通知）

mock：占位返回 ok。真支付时：验签 → 解析 order_id → 更新订单状态（paid + 发卡）。
"""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/cms/payments", tags=["cms-payment"])


@router.post("/notify/{gateway_name}")
async def payment_notify(gateway_name: str, request: Request):
    """支付网关异步回调（占位：真支付时验签 + 更新订单 + 发卡）"""
    # TODO 真支付：验签 → 解析 order_id/amount → 幂等标记 paid → 触发发卡
    return {"gateway": gateway_name, "received": True}
