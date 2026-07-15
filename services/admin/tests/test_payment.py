"""支付网关测试（MockGateway pay/refund/query 接口完整性）。"""
import pytest


@pytest.mark.asyncio
async def test_mock_gateway_pay_refund_query():
    """MockGateway 实现 pay/refund/query 三方法（真支付时替换为 Wechat/Alipay 实现）。"""
    from app.services.payment import MockGateway

    g = MockGateway()
    # pay
    r = await g.pay(order_id=1, amount=100, subject="测试订单")
    assert r.success
    assert "mock_" in r.transaction_id
    # refund
    rf = await g.refund(order_id=1, transaction_id=r.transaction_id)
    assert rf.success
    assert "refund" in rf.transaction_id
    # query
    q = await g.query(order_id=1, transaction_id=r.transaction_id)
    assert q.success
    assert q.message
