"""ProductOrder status 字段 + effective_status / is_paid hybrid property 测试

P0 Day 1.2.1（2026-07-15）— CMS 真支付接入前置：
- status 字段（NEW）：7 状态机
- pay_status 字段（LEGACY）：保留兼容窗口
- effective_status 属性：API 响应统一字段
- is_paid 属性：业务判断"已支付事实"

覆盖：默认值、字段读写、属性映射、边界值。
"""
from datetime import datetime

import pytest

from app.models.cms import ProductOrder


class _Fixture:
    """极简订单构造器，避免依赖完整 session（hybrid_property 不需 flush 即可读）"""

    @staticmethod
    def make(
        status: str | None = None,
        pay_status: str = "pending",
        product_id: int = 1,
        quantity: int = 1,
    ) -> ProductOrder:
        """构造一个未持久化的 ProductOrder 实例。

        不走 session.add；hybrid_property 是 Python 级属性，直接读 self 即可。
        """
        order = ProductOrder(
            product_id=product_id,
            quantity=quantity,
            unit_price=100,
            original_total=100,
            total=100,
            buyer_name="张三",
            buyer_phone="13800138000",
            pay_status=pay_status,
        )
        if status is not None:
            order.status = status
        return order


# ─────────────────────────────────────────────────────────────────────
# 1. 默认值测试
# ─────────────────────────────────────────────────────────────────────


def test_status_default_pending():
    """新建 ProductOrder，status 默认 'pending'"""
    order = _Fixture.make()
    # 字段层默认（Column default 在 SQLAlchemy flush 时生效；实例直读为 None）
    # 但 effective_status 应回退到 pay_status → 'pending'
    assert order.effective_status == "pending"


def test_pay_status_default_pending():
    """LEGACY pay_status 字段保持默认 'pending'"""
    order = _Fixture.make()
    assert order.pay_status == "pending"


def test_pay_status_legacy_compat():
    """旧 pay_status 字段仍可读写"""
    order = _Fixture.make()
    order.pay_status = "paid"
    assert order.pay_status == "paid"
    order.pay_status = "cancelled"
    assert order.pay_status == "cancelled"


# ─────────────────────────────────────────────────────────────────────
# 2. effective_status 行为
# ─────────────────────────────────────────────────────────────────────


def test_effective_status_from_status():
    """status='paid' → effective_status='paid'（优先读新字段）"""
    order = _Fixture.make(status="paid", pay_status="pending")
    assert order.effective_status == "paid"


def test_effective_status_priority_over_legacy():
    """status 优先于 pay_status（即使 pay_status 是 paid）"""
    order = _Fixture.make(status="cancelled", pay_status="paid")
    assert order.effective_status == "cancelled"


def test_effective_status_legacy_fallback():
    """status=None + pay_status='paid' → effective_status='paid'（兼容老数据）"""
    order = _Fixture.make(status=None, pay_status="paid")
    # 注意：实例未 flush，status 默认是 None（Column default 在 flush 才生效）
    assert order.effective_status == "paid"


def test_effective_status_cancelled_fallback():
    """status=None + pay_status='cancelled' → effective_status='cancelled'"""
    order = _Fixture.make(status=None, pay_status="cancelled")
    assert order.effective_status == "cancelled"


def test_effective_status_unknown_fallback():
    """status=None + pay_status='unknown' → effective_status='pending'（默认值兜底）"""
    order = _Fixture.make(status=None, pay_status="unknown")
    assert order.effective_status == "pending"


def test_effective_status_both_empty():
    """status=None + pay_status=None → effective_status='pending'（双兜底）"""
    order = _Fixture.make()
    order.status = None
    order.pay_status = None  # type: ignore[assignment]
    assert order.effective_status == "pending"


# ─────────────────────────────────────────────────────────────────────
# 3. 7 状态值全部可读写
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status_value",
    ["pending", "paid", "card_issuing", "fulfilled", "failed", "cancelled", "refunded"],
)
def test_seven_status_values_writable(status_value):
    """7 状态机值均可写入 status 字段"""
    order = _Fixture.make(status=status_value)
    assert order.status == status_value
    assert order.effective_status == status_value


# ─────────────────────────────────────────────────────────────────────
# 4. is_paid 行为
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status_value",
    ["paid", "card_issuing", "fulfilled", "failed", "refunded"],
)
def test_is_paid_true_for_post_paid_states(status_value):
    """paid/card_issuing/fulfilled/failed/refunded → is_paid=True"""
    order = _Fixture.make(status=status_value)
    assert order.is_paid is True


@pytest.mark.parametrize(
    "status_value",
    ["pending", "cancelled"],
)
def test_is_paid_false_for_unpaid_states(status_value):
    """pending/cancelled → is_paid=False"""
    order = _Fixture.make(status=status_value)
    assert order.is_paid is False


def test_is_paid_legacy_paid_via_pay_status():
    """status=None + pay_status='paid' → is_paid=True（兼容老数据）"""
    order = _Fixture.make(status=None, pay_status="paid")
    assert order.is_paid is True


def test_is_paid_legacy_pending():
    """status=None + pay_status='pending' → is_paid=False"""
    order = _Fixture.make(status=None, pay_status="pending")
    assert order.is_paid is False


# ─────────────────────────────────────────────────────────────────────
# 5. 字段独立性 + 数据库列存在性
# ─────────────────────────────────────────────────────────────────────


def test_status_field_exists_in_table():
    """status 字段在 cms_product_order 表上注册（迁移前置校验）"""
    from sqlalchemy import inspect

    cols = {c.name for c in ProductOrder.__table__.columns}
    assert "status" in cols, "ProductOrder 必须有 status 列"
    assert "pay_status" in cols, "ProductOrder 必须保留 pay_status 列（兼容窗口）"


def test_status_indexed():
    """status 列被索引（业务高频过滤）"""
    from sqlalchemy import inspect

    indexed = {c.name for c in ProductOrder.__table__.indexes}
    indexed_cols: set[str] = set()
    for idx in ProductOrder.__table__.indexes:
        for col in idx.columns:
            indexed_cols.add(col.name)
    assert "status" in indexed_cols, "status 列必须建索引"


def test_status_nullable_true():
    """status 字段 nullable=True（老数据无需 backfill）"""
    status_col = ProductOrder.__table__.columns["status"]
    assert status_col.nullable is True


def test_status_default_pending_string():
    """status 字段默认值 'pending'（字符串）"""
    status_col = ProductOrder.__table__.columns["status"]
    assert status_col.default is not None
    # Column default 在 server_default=None 时是 ColumnDefault 对象
    default_val = status_col.default.arg if hasattr(status_col.default, "arg") else None
    assert default_val == "pending"


# ─────────────────────────────────────────────────────────────────────
# 6. 端到端业务场景（mock 行为，不走真支付）
# ─────────────────────────────────────────────────────────────────────


def test_full_lifecycle_status_transitions():
    """完整生命周期：pending → paid → card_issuing → fulfilled"""
    order = _Fixture.make(status="pending")
    assert order.is_paid is False

    order.status = "paid"
    assert order.effective_status == "paid"
    assert order.is_paid is True

    order.status = "card_issuing"
    assert order.effective_status == "card_issuing"
    assert order.is_paid is True  # 履约中仍算已支付事实

    order.status = "fulfilled"
    assert order.effective_status == "fulfilled"
    assert order.is_paid is True

    # paid_at 字段独立维护（不强制耦合）
    order.paid_at = datetime.utcnow()
    assert order.paid_at is not None


def test_refund_flow():
    """退款：fulfilled → refunded（仍算 paid fact，业务决定不二次发卡）"""
    order = _Fixture.make(status="fulfilled")
    assert order.is_paid is True

    order.status = "refunded"
    assert order.effective_status == "refunded"
    assert order.is_paid is True


def test_failed_fulfillment_recovery():
    """履约失败：card_issuing → failed → card_issuing（重试）"""
    order = _Fixture.make(status="card_issuing")
    order.status = "failed"
    assert order.effective_status == "failed"
    assert order.is_paid is True  # 支付事实不变

    # 重试：failed → card_issuing
    order.status = "card_issuing"
    assert order.effective_status == "card_issuing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])