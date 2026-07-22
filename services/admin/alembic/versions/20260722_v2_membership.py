"""V2.0 客户权益表（M3.2：激活 confirm 后建，核销 used）

Revision ID: v2_mem_p7
Revises: v2_tour_p6
Create Date: 2026-07-22

新建 v2_membership（客户套餐权益：来源授权码激活；active → used/expired）。
"""
import sqlalchemy as sa
from alembic import op

revision: str = "v2_mem_p7"
down_revision: str = "v2_tour_p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_membership",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "customer_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("activation_code_id", sa.BigInteger, nullable=False),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("cms_tour_product.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("activated_at", sa.DateTime, nullable=False),
        sa.Column("used_at", sa.DateTime),
        sa.Column("reservation_id", sa.BigInteger),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index(
        "ix_v2_membership_customer_user_id", "v2_membership", ["customer_user_id"]
    )
    op.create_index(
        "ix_v2_membership_activation_code_id", "v2_membership", ["activation_code_id"]
    )
    op.create_index("ix_v2_membership_status", "v2_membership", ["status"])


def downgrade() -> None:
    op.drop_index("ix_v2_membership_status", table_name="v2_membership")
    op.drop_index(
        "ix_v2_membership_activation_code_id", table_name="v2_membership"
    )
    op.drop_index(
        "ix_v2_membership_customer_user_id", table_name="v2_membership"
    )
    op.drop_table("v2_membership")
