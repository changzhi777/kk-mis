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
    """支付网关接口：真支付实现此接口替换 MockGateway。

    pay: 支付；refund: 退款；query: 查询订单状态（真支付时对接微信/支付宝 API + 验签）。
    """

    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult: ...

    async def refund(
        self, order_id: int, transaction_id: str, amount=None
    ) -> PaymentResult: ...

    async def query(self, order_id: int, transaction_id: str = "") -> PaymentResult: ...


class MockGateway:
    """mock 支付（直接成功，开发/测试用）。

    refund/query 同步 stub，保持接口完整，真支付时替换为 WechatGateway/AlipayGateway。
    """

    async def pay(self, order_id: int, amount, subject: str = "") -> PaymentResult:
        return PaymentResult(
            success=True,
            transaction_id=f"mock_{order_id}_{int(time.time())}",
            message="mock 支付成功",
        )

    async def refund(
        self, order_id: int, transaction_id: str, amount=None
    ) -> PaymentResult:
        return PaymentResult(
            success=True,
            transaction_id=f"mock_refund_{order_id}_{int(time.time())}",
            message="mock 退款成功",
        )

    async def query(self, order_id: int, transaction_id: str = "") -> PaymentResult:
        return PaymentResult(
            success=True,
            transaction_id=transaction_id,
            message="mock 查询成功（已支付）",
        )


# 全局网关（真支付时替换）
gateway: PaymentGateway = MockGateway()


def set_gateway(g: PaymentGateway) -> None:
    """切换支付网关（部署/测试注入用）"""
    global gateway
    gateway = g
