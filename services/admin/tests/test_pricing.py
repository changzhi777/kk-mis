"""VIP 折扣阶梯函数 + 年度返佣阶梯匹配（pricing.py）"""


def test_compute_vip_discount_default_unit_price():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount, DEFAULT_VIP_UNIT_PRICE

    assert DEFAULT_VIP_UNIT_PRICE == Decimal("1888.00")


def test_compute_vip_discount_tier_70_under_100():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    # 1 张 → 70 折
    tier, unit_price, pct = compute_vip_discount(1)
    assert tier == "70"
    assert pct == Decimal("0.70")
    # 1888 × 0.7 = 1321.6
    assert unit_price == Decimal("1321.60")


def test_compute_vip_discount_tier_70_at_99():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    tier, unit_price, pct = compute_vip_discount(99)
    assert tier == "70"
    assert pct == Decimal("0.70")
    assert unit_price == Decimal("1321.60")


def test_compute_vip_discount_tier_60_at_100():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    tier, unit_price, pct = compute_vip_discount(100)
    assert tier == "60"
    assert pct == Decimal("0.60")
    # 1888 × 0.6 = 1132.8
    assert unit_price == Decimal("1132.80")


def test_compute_vip_discount_tier_60_at_999():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    tier, unit_price, pct = compute_vip_discount(999)
    assert tier == "60"
    assert pct == Decimal("0.60")
    assert unit_price == Decimal("1132.80")


def test_compute_vip_discount_tier_50_at_1000():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    tier, unit_price, pct = compute_vip_discount(1000)
    assert tier == "50"
    assert pct == Decimal("0.50")
    # 1888 × 0.5 = 944.0
    assert unit_price == Decimal("944.00")


def test_compute_vip_discount_tier_50_large_quantity():
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    tier, unit_price, pct = compute_vip_discount(5000)
    assert tier == "50"
    assert pct == Decimal("0.50")
    assert unit_price == Decimal("944.00")


def test_compute_vip_discount_custom_unit_price():
    """非 VIP 默认单价时正确计算"""
    from decimal import Decimal

    from app.services.pricing import compute_vip_discount

    # 100 张 × 99 元 → 6 折
    tier, unit_price, pct = compute_vip_discount(100, Decimal("99.00"))
    assert tier == "60"
    assert unit_price == Decimal("59.40")
    assert pct == Decimal("0.60")


def test_compute_vip_discount_invalid_quantity():
    from app.services.pricing import compute_vip_discount

    import pytest

    with pytest.raises(ValueError, match="quantity 必须 ≥ 1"):
        compute_vip_discount(0)
    with pytest.raises(ValueError, match="quantity 必须 ≥ 1"):
        compute_vip_discount(-5)


# ── 年度返佣阶梯匹配 ──


def test_compute_yearly_tier_t1_under_50w():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    rules = [
        (Decimal("0"), Decimal("500000"), Decimal("0.30")),
        (Decimal("500000"), Decimal("2000000"), Decimal("0.40")),
        (Decimal("2000000"), None, Decimal("0.50")),
    ]
    tier, pct = compute_yearly_tier(Decimal("100000"), rules)  # 10 万
    assert tier == "T1"
    assert pct == Decimal("0.30")


def test_compute_yearly_tier_t1_at_boundary_499999():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    rules = [
        (Decimal("0"), Decimal("500000"), Decimal("0.30")),
        (Decimal("500000"), Decimal("2000000"), Decimal("0.40")),
        (Decimal("2000000"), None, Decimal("0.50")),
    ]
    tier, pct = compute_yearly_tier(Decimal("499999"), rules)
    assert tier == "T1"
    assert pct == Decimal("0.30")


def test_compute_yearly_tier_t2_at_50w():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    rules = [
        (Decimal("0"), Decimal("500000"), Decimal("0.30")),
        (Decimal("500000"), Decimal("2000000"), Decimal("0.40")),
        (Decimal("2000000"), None, Decimal("0.50")),
    ]
    tier, pct = compute_yearly_tier(Decimal("500000"), rules)
    assert tier == "T2"
    assert pct == Decimal("0.40")


def test_compute_yearly_tier_t2_at_100w():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    rules = [
        (Decimal("0"), Decimal("500000"), Decimal("0.30")),
        (Decimal("500000"), Decimal("2000000"), Decimal("0.40")),
        (Decimal("2000000"), None, Decimal("0.50")),
    ]
    tier, pct = compute_yearly_tier(Decimal("1000000"), rules)
    assert tier == "T2"
    assert pct == Decimal("0.40")


def test_compute_yearly_tier_t3_above_200w():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    rules = [
        (Decimal("0"), Decimal("500000"), Decimal("0.30")),
        (Decimal("500000"), Decimal("2000000"), Decimal("0.40")),
        (Decimal("2000000"), None, Decimal("0.50")),
    ]
    tier, pct = compute_yearly_tier(Decimal("5000000"), rules)  # 500 万
    assert tier == "T3"
    assert pct == Decimal("0.50")


def test_compute_yearly_tier_empty_rules():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    tier, pct = compute_yearly_tier(Decimal("1000"), [])
    assert tier == "T0"
    assert pct == Decimal("0")


def test_compute_yearly_tier_zero_sales_returns_t0():
    from decimal import Decimal

    from app.services.pricing import compute_yearly_tier

    rules = [(Decimal("0"), Decimal("500000"), Decimal("0.30"))]
    tier, pct = compute_yearly_tier(Decimal("0"), rules)
    # cumulative = 0 满足 min_sales=0 → 命中 T1
    # 这是合法的（最小档），不是 T0
    assert tier == "T1"
    assert pct == Decimal("0.30")