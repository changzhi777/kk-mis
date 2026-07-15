"""CMS 真支付 webhook P0 数据底座。

Revision ID: 20260715_cms_payment_webhook_p0
Revises:
Create Date: 2026-07-15

2026-07-15 Day 1.1.1 修正（与 P0 Day 1.2.1 模型对齐）：
1. status 改 nullable=True（与模型对齐，让旧 pay_status 行无需 backfill；
   effective_status hybrid_property 自动从 pay_status 回退）。
2. paid_at 字段不再在迁移中创建（模型已有，本迁移复用即可）。
3. (payment_provider, payment_id) 唯一约束改为部分唯一索引
   WHERE payment_id IS NOT NULL；支持 mock 模式 payment_id 为空。
   同时 payment_id 列改 nullable=True 以允许 mock 场景写入 NULL。
4. 移除 DROP pay_status 步骤——业务代码仍写 pay_status，
   待 Day 1.2.2 业务代码改造完成后再单独 migration 移除。
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

    # 2. 新增订单 status，nullable=True 与 Day 1.2.1 模型对齐。
    # 历史数据保持 pay_status 原样，effective_status 属性自动从 pay_status 回退；
    # 不强制 NOT NULL + server_default，让旧 pay_status 行无需 backfill。
    op.add_column(
        "cms_product_order",
        sa.Column(
            "status",
            _status_type(dialect_name),
            nullable=True,
            server_default=sa.text("'pending'"),
        ),
    )

    # 3. 仅迁移旧状态机可识别的值，其他历史值保留为 pending。
    # pay_status 列保留（LEGACY 字段，兼容窗口约 2-3 个月至 2026-09，
    # 待 Day 1.2.2 业务代码改造完成后单独 migration 移除），
    # 这里只是用旧 pay_status 值给新 status 列做一次回填，让历史数据就位。
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

    # 4. 仅建新 status 索引；pay_status 列与旧索引保留不动。
    op.create_index(
        "idx_cms_product_order_status",
        "cms_product_order",
        ["status"],
        unique=False,
    )

    # 5. 支付通知幂等表：payment_id 可空（mock 模式无支付流水号），
    # 真支付场景下 (payment_provider, payment_id) 必须唯一。
    # 采用部分唯一索引 WHERE payment_id IS NOT NULL，
    # 既保证业务幂等，又允许 mock 模式下多条 NULL 共存。
    op.create_table(
        "cms_payment_idempotency",
        sa.Column("id", _bigint_pk(), primary_key=True, autoincrement=True),
        sa.Column("payment_provider", sa.String(length=20), nullable=False),
        sa.Column("payment_id", sa.String(length=128), nullable=True),
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
    )
    # 部分唯一索引：PG 与 SQLite 都支持 partial index；
    # 业务幂等仅对真支付数据生效，mock NULL 行不受约束。
    op.create_index(
        "uq_cms_payment_idempotency",
        "cms_payment_idempotency",
        ["payment_provider", "payment_id"],
        unique=True,
        postgresql_where=sa.text("payment_id IS NOT NULL"),
        sqlite_where=sa.text("payment_id IS NOT NULL"),
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
    """删除 P0 新表、新索引与新 status 列。

    注意：pay_status 列从 upgrade 起就一直保留，downgrade 不需要重建。
    """
    dialect_name = _dialect_name()
    bind = op.get_bind()

    # 1. 按外键依赖逆序删除新表及其索引。
    op.drop_index("idx_cms_order_card_order", table_name="cms_order_card")
    op.drop_table("cms_order_card")

    op.drop_index("idx_cms_webhook_retry_status", table_name="cms_webhook_retry")
    op.drop_table("cms_webhook_retry")

    # 部分唯一索引必须先于 drop_table 显式删除（迁移不会自动收）。
    op.drop_index(
        "uq_cms_payment_idempotency",
        table_name="cms_payment_idempotency",
    )
    op.drop_index(
        "idx_cms_payment_idempotency_order",
        table_name="cms_payment_idempotency",
    )
    op.drop_index(
        "idx_cms_payment_idempotency_expires",
        table_name="cms_payment_idempotency",
    )
    op.drop_table("cms_payment_idempotency")

    # 2. 新状态兼容映射到旧 pending|paid|cancelled 三态。
    # （pay_status 列在 upgrade 中未被删除，无需 add_column；这里 idempotent 写回）
    op.execute(
        "UPDATE cms_product_order SET pay_status = CASE "
        "WHEN status IN ('paid', 'card_issuing', 'fulfilled', 'failed') THEN 'paid' "
        "WHEN status IN ('refunded', 'cancelled') THEN 'cancelled' "
        "ELSE 'pending' END"
    )

    # 3. 删除新 status 索引与列；SQLite 通过 batch 重建表。
    op.drop_index("idx_cms_product_order_status", table_name="cms_product_order")
    if dialect_name == "sqlite":
        with op.batch_alter_table("cms_product_order", recreate="always") as batch_op:
            batch_op.drop_column("status")
    else:
        op.drop_column("cms_product_order", "status")

    # 4. PostgreSQL 最后删除 ENUM；SQLite 无独立类型对象。
    if dialect_name == "postgresql":
        postgresql.ENUM(
            *ORDER_STATUS_VALUES,
            name=ORDER_STATUS_ENUM,
        ).drop(bind, checkfirst=True)
