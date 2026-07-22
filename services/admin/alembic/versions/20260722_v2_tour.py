"""V2.0 团期 + 资源库存 + 客户预约（M3.1：预约团期 b-简）

Revision ID: v2_tour_p6
Revises: v2_rebate_p5
Create Date: 2026-07-22

新建 v2_tour_group（团期）/ v2_resource_stock（房+车库存 b-简）/ v2_reservation（客户预约）。
"""
import sqlalchemy as sa
from alembic import op

revision: str = "v2_tour_p6"
down_revision: str = "v2_rebate_p5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_tour_group",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("cms_tour_product.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("start_date", sa.DateTime, nullable=False),
        sa.Column("end_date", sa.DateTime, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("booked", sa.Integer, server_default="0", nullable=False),
        sa.Column("status", sa.String(16), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_v2_tour_group_product_id", "v2_tour_group", ["product_id"])
    op.create_index("ix_v2_tour_group_status", "v2_tour_group", ["status"])

    op.create_table(
        "v2_resource_stock",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "tour_group_id",
            sa.BigInteger,
            sa.ForeignKey("v2_tour_group.id"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(16), nullable=False),
        sa.Column("total_qty", sa.Integer, nullable=False),
        sa.Column("used_qty", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.UniqueConstraint(
            "tour_group_id", "resource_type", name="uq_v2_resource_group_type"
        ),
    )
    op.create_index(
        "ix_v2_resource_stock_tour_group_id", "v2_resource_stock", ["tour_group_id"]
    )

    op.create_table(
        "v2_reservation",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "customer_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "tour_group_id",
            sa.BigInteger,
            sa.ForeignKey("v2_tour_group.id"),
            nullable=False,
        ),
        sa.Column("activation_code_id", sa.BigInteger),
        sa.Column("people_count", sa.Integer, nullable=False),
        sa.Column("hotel_qty", sa.Integer, server_default="0", nullable=False),
        sa.Column("car_qty", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "status", sa.String(16), server_default="confirmed", nullable=False
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index(
        "ix_v2_reservation_customer_user_id", "v2_reservation", ["customer_user_id"]
    )
    op.create_index(
        "ix_v2_reservation_tour_group_id", "v2_reservation", ["tour_group_id"]
    )
    op.create_index("ix_v2_reservation_status", "v2_reservation", ["status"])


def downgrade() -> None:
    op.drop_index("ix_v2_reservation_status", table_name="v2_reservation")
    op.drop_index("ix_v2_reservation_tour_group_id", table_name="v2_reservation")
    op.drop_index(
        "ix_v2_reservation_customer_user_id", table_name="v2_reservation"
    )
    op.drop_table("v2_reservation")
    op.drop_index(
        "ix_v2_resource_stock_tour_group_id", table_name="v2_resource_stock"
    )
    op.drop_table("v2_resource_stock")
    op.drop_index("ix_v2_tour_group_status", table_name="v2_tour_group")
    op.drop_index("ix_v2_tour_group_product_id", table_name="v2_tour_group")
    op.drop_table("v2_tour_group")
