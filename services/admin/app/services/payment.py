"""支付网关抽象 + mock 实现

真支付（微信/支付宝）上线时：
1. 实现 PaymentGateway 的 WechatGateway / AlipayGateway（调真 API + 验签）
2. settings 配商户号 / API 密钥 / 回调 URL
3. 启动时 set_gateway(真实现) 或改全局 gateway
"""
import time
from typing import Protocol


class PaymentResult:
    def __init__(self, success: bool, transaction_id: str = "", message: str = ""):
        self.success = success
        self.transaction_id = transaction_id
        self.message = message


class PaymentGateway(Protocol):
    """支付网关接口：真支付实现此接口替换 MockGateway"""

    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult:
        ...


class MockGateway:
    """mock 支付（直接成功，开发/测试用）"""

    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult:
        return PaymentResult(
            success=True,
            transaction_id=f"mock_{order_id}_{int(time.time())}",
            message="mock 支付成功",
        )


# 全局网关（真支付时替换）
gateway: PaymentGateway = MockGateway()


def set_gateway(g: PaymentGateway) -> None:
    """切换支付网关（部署/测试注入用）"""
    global gateway
    gateway = g
