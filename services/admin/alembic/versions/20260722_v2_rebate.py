"""V2.0 经销商阶梯返点记录表（M2.4：月结返余额）

Revision ID: v2_rebate_p5
Revises: v2_real_p4
Create Date: 2026-07-22

新建 v2_rebate_record（agent_id + period 唯一；月度激活消费额 → 阶梯返点 → 返余额）。
"""
import sqlalchemy as sa
from alembic import op

revision: str = "v2_rebate_p5"
down_revision: str = "v2_real_p4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_rebate_record",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("agent_id", sa.BigInteger, sa.ForeignKey("agent.id"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("total_sales", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("tier", sa.String(16)),
        sa.Column("rebate_pct", sa.Numeric(5, 4), server_default="0", nullable=False),
        sa.Column(
            "rebate_amount", sa.Numeric(14, 2), server_default="0", nullable=False
        ),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("settled_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.UniqueConstraint("agent_id", "period", name="uq_v2_rebate_agent_period"),
    )
    op.create_index("ix_v2_rebate_record_agent_id", "v2_rebate_record", ["agent_id"])
    op.create_index("ix_v2_rebate_record_period", "v2_rebate_record", ["period"])
    op.create_index("ix_v2_rebate_record_status", "v2_rebate_record", ["status"])


def downgrade() -> None:
    op.drop_index("ix_v2_rebate_record_status", table_name="v2_rebate_record")
    op.drop_index("ix_v2_rebate_record_period", table_name="v2_rebate_record")
    op.drop_index("ix_v2_rebate_record_agent_id", table_name="v2_rebate_record")
    op.drop_table("v2_rebate_record")
