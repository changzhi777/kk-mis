"""CMS 支付异常事件持久化表（P0 Day 2.1 缺口 #4）。

Revision ID: 20260715_cms_payment_exception_event_p1
Revises: 20260715_cms_payment_webhook_p0
Create Date: 2026-07-15

2026-07-15 缺口 #4 修复新增 cms_payment_exception_event 表：
- 支付确认冲突（金额不符/状态非法/订单不存在）：severity=warning 或 critical
- webhook 重试耗尽（attempts 达 MAX_RETRY_ATTEMPTS）：severity=critical（告警）
- webhook 解析失败（验签/JSON）：severity=warning

设计要点：
- 不影响现有 P0 Day 1 数据，新表独立创建；
- PG/SQLite 方言兼容，参照 20260715_cms_payment_webhook_p0 风格；
- 列定义严格对齐 models/cms.py::PaymentExceptionEvent。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# Alembic revision identifiers.
revision: str = "20260715_cms_payment_exception_event_p1"
down_revision: str | Sequence[str] | None = "20260715_cms_payment_webhook_p0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _dialect_name() -> str:
    """通过 SQLAlchemy inspector 识别迁移目标数据库。"""
    bind = op.get_bind()
    try:
        dialect_name = str(inspect(bind).dialect.name)
    except sa.exc.NoInspectionAvailable:
        # 支持 `alembic upgrade head --sql` 的离线 MockConnection。
        dialect_name = str(bind.dialect.name)

    if dialect_name not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"CMS 异常事件迁移不支持数据库方言: {dialect_name}")
    return dialect_name


def _bigint_pk() -> sa.types.TypeEngine:
    """PostgreSQL 生成 BIGSERIAL，SQLite 使用可自增的 INTEGER PRIMARY KEY。"""
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """创建 cms_payment_exception_event 表 + 索引（PG/SQLite 兼容）。"""
    # 不依赖方言特性，单一分支即可
    op.create_table(
        "cms_payment_exception_event",
        sa.Column("id", _bigint_pk(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("payment_id", sa.String(length=100), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'warning'"),
        ),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["cms_product_order.id"],
            name="fk_cms_payment_exception_event_order",
        ),
    )

    # 单列索引（与模型 __table_args__ 对齐）
    op.create_index(
        "idx_cms_payment_exception_event_type",
        "cms_payment_exception_event",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "idx_cms_payment_exception_event_order",
        "cms_payment_exception_event",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "idx_cms_payment_exception_event_payment",
        "cms_payment_exception_event",
        ["payment_id"],
        unique=False,
    )
    op.create_index(
        "idx_cms_payment_exception_event_created_at",
        "cms_payment_exception_event",
        ["created_at"],
        unique=False,
    )

    # 组合索引：按事件类型 + 时间窗查询告警历史
    op.create_index(
        "idx_cms_payment_exception_event_type_time",
        "cms_payment_exception_event",
        ["event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """删除 cms_payment_exception_event 表及其索引。"""
    op.drop_index(
        "idx_cms_payment_exception_event_type_time",
        table_name="cms_payment_exception_event",
    )
    op.drop_index(
        "idx_cms_payment_exception_event_created_at",
        table_name="cms_payment_exception_event",
    )
    op.drop_index(
        "idx_cms_payment_exception_event_payment",
        table_name="cms_payment_exception_event",
    )
    op.drop_index(
        "idx_cms_payment_exception_event_order",
        table_name="cms_payment_exception_event",
    )
    op.drop_index(
        "idx_cms_payment_exception_event_type",
        table_name="cms_payment_exception_event",
    )
    op.drop_table("cms_payment_exception_event")
