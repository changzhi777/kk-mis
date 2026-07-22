"""V2.0 授权码表 + User.user_type（M2.1/2.2）

Revision ID: v2_act_p3
Revises: v2_dealer_q2
Create Date: 2026-07-22

新建 v2_activation_code（客户授权码：5-10min 时效 + 一次性 + 客户生成/经销商发起/客户确认）；
users 加 user_type（V2.0 统一用户模型 customer/dealer，默认 customer）。
"""
import sqlalchemy as sa
from alembic import op

revision: str = "v2_act_p3"
down_revision: str = "v2_dealer_q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users 加 user_type（V2.0 统一用户模型；现有用户默认 customer）
    op.add_column(
        "users",
        sa.Column("user_type", sa.String(16), server_default="customer", nullable=False),
    )
    op.create_index("ix_users_user_type", "users", ["user_type"])

    # 2. v2_activation_code（客户授权码）
    op.create_table(
        "v2_activation_code",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column(
            "customer_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("agent_id", sa.BigInteger, sa.ForeignKey("agent.id"), nullable=False),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("cms_tour_product.id"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("initiated_at", sa.DateTime),
        sa.Column("activated_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("code", name="uq_v2_activation_code"),
    )
    op.create_index("ix_v2_activation_code_code", "v2_activation_code", ["code"])
    op.create_index(
        "ix_v2_activation_code_customer_user_id",
        "v2_activation_code",
        ["customer_user_id"],
    )
    op.create_index("ix_v2_activation_code_agent_id", "v2_activation_code", ["agent_id"])
    op.create_index(
        "ix_v2_activation_code_status", "v2_activation_code", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_v2_activation_code_status", table_name="v2_activation_code")
    op.drop_index("ix_v2_activation_code_agent_id", table_name="v2_activation_code")
    op.drop_index(
        "ix_v2_activation_code_customer_user_id", table_name="v2_activation_code"
    )
    op.drop_index("ix_v2_activation_code_code", table_name="v2_activation_code")
    op.drop_table("v2_activation_code")
    op.drop_index("ix_users_user_type", table_name="users")
    op.drop_column("users", "user_type")
