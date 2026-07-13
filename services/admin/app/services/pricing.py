"""VIP 卡定价 + 年度返佣阶梯服务（决策 #3 重构 2026-07-13）。

VIP 单卡单价：1888.00 元
数量阶梯折扣：
  - 1-99 张 → 7 折（unit_price × 0.7）
  - 100-999 张 → 6 折（unit_price × 0.6）
  - 1000+ 张 → 5 折（unit_price × 0.5）

年度累计返佣阶梯（默认 seed）：
  - T1: < 50 万 → 30%
  - T2: 50-200 万 → 40%
  - T3: > 200 万 → 50%
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import YearlyCommissionRule

# VIP 单卡标准单价（可被 AssetCardBatch.unit_price 覆盖）
DEFAULT_VIP_UNIT_PRICE = Decimal("1888.00")

# 决策 #3：commission_rate 硬上限 0.5（防全额返利）
MAX_COMMISSION_RATE = Decimal("0.5")


# ── 数量折扣（纯函数） ────────────────────────────────────────────────


def compute_vip_discount(
    quantity: int,
    unit_price: Optional[Decimal] = None,
) -> tuple[str, Decimal, Decimal]:
    """按数量阶梯计算折扣。

    Args:
        quantity: 进货数量（≥1）
        unit_price: VIP 单卡原价（默认 1888.00）

    Returns:
        (tier, unit_price_actual, discount_pct)
        - tier: 'full' / '70' / '60' / '50'（折扣档标识）
        - unit_price_actual: 折扣后单价
        - discount_pct: 折扣比例（如 0.7）
    """
    if quantity <= 0:
        raise ValueError("quantity 必须 ≥ 1")
    if unit_price is None:
        unit_price = DEFAULT_VIP_UNIT_PRICE

    if quantity >= 1000:
        return ("50", (unit_price * Decimal("0.50")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), Decimal("0.50"))
    elif quantity >= 100:
        return ("60", (unit_price * Decimal("0.60")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), Decimal("0.60"))
    else:
        return (
            "70",
            (unit_price * Decimal("0.70")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            Decimal("0.70"),
        )


# ── 年度返佣阶梯（DB + 纯函数） ────────────────────────────────────────


async def load_active_yearly_rules(
    session: AsyncSession,
) -> list[tuple[Decimal, Optional[Decimal], Decimal]]:
    """加载所有 active 年度返佣阶梯规则（按 min_sales 升序）。

    Returns: list[(min_sales, max_sales, commission_pct), ...]
    """
    rows = (
        await session.execute(
            select(YearlyCommissionRule)
            .where(YearlyCommissionRule.status.is_(True))
            .order_by(YearlyCommissionRule.min_sales.asc())
        )
    ).scalars().all()
    return [
        (Decimal(str(r.min_sales)), Decimal(str(r.max_sales)) if r.max_sales else None, Decimal(str(r.commission_pct)))
        for r in rows
    ]


def compute_yearly_tier(
    cumulative_sales: Decimal,
    rules: list[tuple[Decimal, Optional[Decimal], Decimal]],
) -> tuple[str, Decimal]:
    """根据累计销售额匹配年度返佣阶梯。

    Args:
        cumulative_sales: 年度累计销售额
        rules: 已按 min_sales 升序排序的阶梯列表 [(min_sales, max_sales, commission_pct), ...]
               max_sales=None 表示上限无限

    Returns:
        (tier_name, commission_pct)
        若无匹配返回 ('T0', Decimal('0'))
    """
    if not rules:
        return ("T0", Decimal("0"))
    # 遍历时记录下标，避免 list.index O(n) 重查 + min_sales 相同时错位
    for idx, (min_s, max_s, pct) in enumerate(rules, start=1):
        if cumulative_sales >= min_s and (max_s is None or cumulative_sales < max_s):
            return (f"T{idx}", pct)
    return ("T0", Decimal("0"))