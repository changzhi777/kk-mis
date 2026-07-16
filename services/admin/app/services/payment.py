"""支付网关抽象 + mock 实现

真支付（微信/支付宝）上线时：
1. 实现 PaymentGateway 的 WechatGateway / AlipayGateway（调真 API + 验签）
2. settings 配商户号 / API 密钥 / 回调 URL
3. 启动时 set_gateway(真实现) 或改全局 gateway

P0 Day 2 缺口 #1 修复（2026-07-16）：
- 新增 build_gateway_from_settings(settings) 工厂：
  mock → MockGateway；wechat → WechatPayV3Gateway.from_settings；alipay → NotImplementedError；未知 → ValueError。
- wechat 实例化失败必须 raise（不 fallback mock），防止 silent corruption。
"""
import time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..config import Settings


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


def build_gateway_from_settings(settings: "Settings") -> PaymentGateway:
    """根据 settings.PAYMENT_PROVIDER 构造对应 PaymentGateway。

    fail-closed 策略（绝不静默 fallback mock）：
    - mock    → MockGateway()                       （永不失败）
    - wechat  → WechatPayV3Gateway.from_settings()  （实例化失败必须 raise）
    - alipay  → NotImplementedError
    - 未知    → ValueError

    风险与设计动机：
    若 PAYMENT_PROVIDER=wechat 但启动时未成功构造 wechat gateway，路由层
    routes/cms/orders.py::pay_order 会用全局 MockGateway 完成 mock 支付并
    写库为真实订单事实 —— silent corruption（资金对账灾难）。

    因此本函数对 wechat 模式不做 fallback，实例化失败立即 raise，
    由 lifespan 决定 fail-closed（拒绝启动，systemd 告警）还是
    fail-open（降级 mock + ERROR 日志 + Prometheus 指标）。

    调用方：lifespan（main.py）。
    """
    provider = (settings.payment_provider or "mock").strip().lower()
    if provider == "mock":
        return MockGateway()
    if provider == "wechat":
        # lazy import 避免无 wechat 凭据时启动即 ImportError
        from .wechat_pay import WechatPayV3Gateway

        return WechatPayV3Gateway.from_settings(settings)
    if provider == "alipay":
        raise NotImplementedError(
            "AlipayGateway 尚未实现；待 P0 Day 2.5 / Day 3 接入"
        )
    raise ValueError(
        f"未知的 PAYMENT_PROVIDER={provider!r}（仅支持 mock|wechat|alipay）"
    )
