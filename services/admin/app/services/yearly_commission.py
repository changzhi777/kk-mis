"""年度返佣结算服务（决策 #3 重构 2026-07-13）。

按自然年累计销售额查阶梯，写 YearlyCommissionRecord。
通常在每年 1 月初调度（或手动触发测试）。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Agent,
    AgentOrder,
    YearlyCommissionRecord,
)
from .pricing import compute_yearly_tier, load_active_yearly_rules

logger = logging.getLogger(__name__)


async def settle_yearly_commissions(
    session: AsyncSession,
    year: int,
    *,
    dry_run: bool = False,
) -> list[YearlyCommissionRecord]:
    """结算指定年份的所有 agent 年度返佣。

    Args:
        session: DB session
        year: 自然年（YYYY）
        dry_run: True 时只计算不写入

    Returns:
        写入的 YearlyCommissionRecord 列表（dry_run 时为空）
    """
    # 1. 加载所有阶梯规则（service 层单一源）
    rules = await load_active_yearly_rules(session)
    if not rules:
        logger.warning("year=%d 无年度返佣阶梯规则，跳过结算", year)
        return []

    # 2. 一次性查所有 active agent + 该年 completed 订单的 SUM/COUNT（避免 N+1）
    # 2a. 所有 active agent
    agents = (
        await session.execute(select(Agent).where(Agent.status.is_(True)))
    ).scalars().all()
    if not agents:
        return []

    # 2b. 一次性聚合各 agent 该年 completed 订单的 SUM(total) + COUNT(*)
    # 用 created_at range scan（走 B-tree 复合索引 (agent_id, created_at, status)）
    # 替代原 func.extract("year", created_at) 全表扫（2026-07-13 性能修复）
    from datetime import datetime as _dt

    year_start = _dt(year, 1, 1)
    year_end = _dt(year + 1, 1, 1)
    aggregate_rows = (
        await session.execute(
            select(
                AgentOrder.agent_id,
                func.coalesce(func.sum(AgentOrder.total), 0).label("total_sales"),
                func.count().label("order_count"),
            )
            .where(
                AgentOrder.created_at >= year_start,
                AgentOrder.created_at < year_end,
                AgentOrder.status == "completed",
            )
            .group_by(AgentOrder.agent_id)
        )
    ).all()
    agent_stats: dict[int, tuple[Decimal, int]] = {
        row.agent_id: (Decimal(str(row.total_sales)), int(row.order_count))
        for row in aggregate_rows
    }

    # 2c. 一次性查已存在记录（按 (agent_id, year)）
    existing_rows = (
        await session.execute(
            select(YearlyCommissionRecord).where(YearlyCommissionRecord.year == year)
        )
    ).scalars().all()
    existing_by_agent: dict[int, YearlyCommissionRecord] = {r.agent_id: r for r in existing_rows}

    # 3. 纯内存循环（无 DB round-trip）
    records: list[YearlyCommissionRecord] = []
    for agent in agents:
        total_sales, order_count = agent_stats.get(agent.id, (Decimal("0"), 0))
        if total_sales <= 0:
            continue

        tier, pct = compute_yearly_tier(total_sales, rules)
        amount = (total_sales * pct).quantize(Decimal("0.01"))

        if dry_run:
            logger.info(
                "[dry-run] agent=%d region=%s total_sales=%s tier=%s pct=%s amount=%s",
                agent.id, agent.region_code, total_sales, tier, pct, amount,
            )
            continue

        # 已存在则更新
        existing = existing_by_agent.get(agent.id)
        if existing:
            existing.total_sales = total_sales
            existing.tier = tier
            existing.commission_pct = pct
            existing.amount = amount
            existing.order_count = order_count
            existing.region_code = agent.region_code
            records.append(existing)
        else:
            rec = YearlyCommissionRecord(
                agent_id=agent.id,
                year=year,
                total_sales=total_sales,
                tier=tier,
                commission_pct=pct,
                amount=amount,
                order_count=order_count,
                payout_status="pending",
                region_code=agent.region_code,
            )
            session.add(rec)
            records.append(rec)

    if not dry_run:
        # 一次 commit（records 已带 PK 默认值；无需逐条 refresh）
        await session.commit()

    return records


async def get_yearly_commissions(
    session: AsyncSession,
    year: int,
    *,
    region_code: str | None = None,
) -> list[YearlyCommissionRecord]:
    """查询年度返佣记录（可按区域过滤）"""
    stmt = select(YearlyCommissionRecord).where(YearlyCommissionRecord.year == year)
    if region_code:
        stmt = stmt.where(YearlyCommissionRecord.region_code == region_code)
    rows = (await session.execute(stmt.order_by(YearlyCommissionRecord.amount.desc()))).scalars().all()
    return list(rows)