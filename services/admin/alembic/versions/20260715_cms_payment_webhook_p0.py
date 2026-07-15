"""CMS 真支付 webhook P0 数据底座。

Revision ID: 20260715_cms_payment_webhook_p0
Revises:
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# Alembic revision identifiers.
revision: str = "20260715_cms_payment_webhook_p0"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_STATUS_ENUM = "cms_order_status"
ORDER_STATUS_VALUES = (
    "pending",
    "paid",
    "card_issuing",
    "fulfilled",
    "failed",
    "refunded",
    "cancelled",
)


def _dialect_name() -> str:
    """通过 SQLAlchemy inspector 识别迁移目标数据库。"""
    bind = op.get_bind()
    try:
        dialect_name = str(inspect(bind).dialect.name)
    except sa.exc.NoInspectionAvailable:
        # 支持 `alembic upgrade head --sql` 的离线 MockConnection。
        dialect_name = str(bind.dialect.name)

    if dialect_name not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"CMS 支付迁移不支持数据库方言: {dialect_name}")
    return dialect_name


def _bigint_pk() -> sa.types.TypeEngine:
    """PostgreSQL 生成 BIGSERIAL，SQLite 使用可自增的 INTEGER PRIMARY KEY。"""
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _status_type(dialect_name: str) -> sa.types.TypeEngine:
    """PostgreSQL 使用原生 ENUM，SQLite 使用 String 保持兼容。"""
    if dialect_name == "postgresql":
        return postgresql.ENUM(
            *ORDER_STATUS_VALUES,
            name=ORDER_STATUS_ENUM,
            create_type=False,
        )
    return sa.String(length=20)


def _json_type(dialect_name: str) -> sa.types.TypeEngine:
    """PostgreSQL 使用 JSONB，SQLite 使用通用 JSON。"""
    if dialect_name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _asset_card_table() -> str:
    """兼容现有项目表名 asset_card 与目标规范表名 asset_cards。"""
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
    except sa.exc.NoInspectionAvailable:
        # 项目模型的实际表名是 asset_card；离线 SQL 也必须可直接执行。
        return "asset_card"

    if inspector.has_table("asset_cards"):
        return "asset_cards"
    if inspector.has_table("asset_card"):
        return "asset_card"
    raise RuntimeError("找不到 asset_cards 或 asset_card，无法创建 cms_order_card 外键")


def upgrade() -> None:
    """迁移订单状态并创建支付幂等、webhook 重试与多卡关联表。"""
    dialect_name = _dialect_name()
    bind = op.get_bind()

    # 1. PostgreSQL 创建原生 ENUM；SQLite 不创建 ENUM。
    if dialect_name == "postgresql":
        postgresql.ENUM(
            *ORDER_STATUS_VALUES,
            name=ORDER_STATUS_ENUM,
        ).create(bind, checkfirst=True)

    # 2. 新增订单 status，历史数据先由服务端默认值 pending 承接。
    op.add_column(
        "cms_product_order",
        sa.Column(
            "status",
            _status_type(dialect_name),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )

    # 3. 仅迁移旧状态机可识别的值，其他历史值保留为 pending。
    if dialect_name == "postgresql":
        op.execute(
            "UPDATE cms_product_order "
            "SET status = pay_status::cms_order_status "
            "WHERE pay_status IN ('pending', 'paid', 'cancelled')"
        )
    else:
        op.execute(
            "UPDATE cms_product_order "
            "SET status = pay_status "
            "WHERE pay_status IN ('pending', 'paid', 'cancelled')"
        )

    # 4. 删除旧索引与 pay_status 列；SQLite 通过 batch 重建表。
    op.drop_index("ix_cms_product_order_pay_status", table_name="cms_product_order")
    if dialect_name == "sqlite":
        with op.batch_alter_table("cms_product_order", recreate="always") as batch_op:
            batch_op.drop_column("pay_status")
    else:
        op.drop_column("cms_product_order", "pay_status")
    op.create_index(
        "idx_cms_product_order_status",
        "cms_product_order",
        ["status"],
        unique=False,
    )

    # 5. 支付通知幂等表：provider + 事件 ID 唯一。
    op.create_table(
        "cms_payment_idempotency",
        sa.Column("id", _bigint_pk(), primary_key=True, autoincrement=True),
        sa.Column("payment_provider", sa.String(length=20), nullable=False),
        sa.Column("payment_id", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("request_body_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_content_type", sa.String(length=100), nullable=True),
        sa.Column("result_status", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["cms_product_order.id"],
            name="fk_cms_payment_idempotency_order",
        ),
        sa.UniqueConstraint(
            "payment_provider",
            "payment_id",
            name="uq_cms_payment_idempotency",
        ),
    )
    op.create_index(
        "idx_cms_payment_idempotency_expires",
        "cms_payment_idempotency",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "idx_cms_payment_idempotency_order",
        "cms_payment_idempotency",
        ["order_id"],
        unique=False,
    )

    # 6. webhook 持久化重试表；P0 保证一单最多一个发卡任务。
    op.create_table(
        "cms_webhook_retry",
        sa.Column("id", _bigint_pk(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", _json_type(dialect_name), nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["cms_product_order.id"],
            name="fk_cms_webhook_retry_order",
        ),
        sa.UniqueConstraint("order_id", name="uq_cms_webhook_retry_order"),
    )
    op.create_index(
        "idx_cms_webhook_retry_status",
        "cms_webhook_retry",
        ["status", "next_retry_at"],
        unique=False,
    )

    # 7. 一单多卡关联表。项目当前实际卡表名为 asset_card。
    asset_card_table = _asset_card_table()
    op.create_table(
        "cms_order_card",
        sa.Column("id", _bigint_pk(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["cms_product_order.id"],
            name="fk_cms_order_card_order",
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            [f"{asset_card_table}.id"],
            name="fk_cms_order_card_card",
        ),
        sa.UniqueConstraint("order_id", "card_id", name="uq_cms_order_card"),
    )
    op.create_index(
        "idx_cms_order_card_order",
        "cms_order_card",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    """删除 P0 新表并把新状态机兼容映射回旧 pay_status。"""
    dialect_name = _dialect_name()
    bind = op.get_bind()

    # 1. 按外键依赖逆序删除新表及其索引。
    op.drop_index("idx_cms_order_card_order", table_name="cms_order_card")
    op.drop_table("cms_order_card")

    op.drop_index("idx_cms_webhook_retry_status", table_name="cms_webhook_retry")
    op.drop_table("cms_webhook_retry")

    op.drop_index(
        "idx_cms_payment_idempotency_order",
        table_name="cms_payment_idempotency",
    )
    op.drop_index(
        "idx_cms_payment_idempotency_expires",
        table_name="cms_payment_idempotency",
    )
    op.drop_table("cms_payment_idempotency")

    # 2. 恢复旧列，先允许 NULL 以便安全回填。
    op.add_column(
        "cms_product_order",
        sa.Column("pay_status", sa.String(length=20), nullable=True),
    )

    # 3. 新状态兼容映射到旧 pending|paid|cancelled 三态。
    op.execute(
        "UPDATE cms_product_order SET pay_status = CASE "
        "WHEN status IN ('paid', 'card_issuing', 'fulfilled', 'failed') THEN 'paid' "
        "WHEN status IN ('refunded', 'cancelled') THEN 'cancelled' "
        "ELSE 'pending' END"
    )

    # 4. 删除新 status，恢复旧列非空约束与索引。
    op.drop_index("idx_cms_product_order_status", table_name="cms_product_order")
    if dialect_name == "sqlite":
        with op.batch_alter_table("cms_product_order", recreate="always") as batch_op:
            batch_op.alter_column(
                "pay_status",
                existing_type=sa.String(length=20),
                nullable=False,
            )
            batch_op.drop_column("status")
    else:
        op.alter_column(
            "cms_product_order",
            "pay_status",
            existing_type=sa.String(length=20),
            nullable=False,
        )
        op.drop_column("cms_product_order", "status")

    op.create_index(
        "ix_cms_product_order_pay_status",
        "cms_product_order",
        ["pay_status"],
        unique=False,
    )

    # 5. PostgreSQL 最后删除 ENUM；SQLite 无独立类型对象。
    if dialect_name == "postgresql":
        postgresql.ENUM(
            *ORDER_STATUS_VALUES,
            name=ORDER_STATUS_ENUM,
        ).drop(bind, checkfirst=True)
