"""V2.0 Agent.source 字段（1user→1agent 加固：区分 V1 区域代理 / V2 经销商）

Revision ID: v2_asrc_p8
Revises: v2_mem_p7
Create Date: 2026-07-22

agent 加 source（v1 区域代理 / v2 经销商，默认 v1）；V2 查询按 source=v2 过滤，
防同一 user 的 V1+V2 agent 共存时 .first() 取错（资金/激活错位）。
"""
import sqlalchemy as sa
from alembic import op

revision: str = "v2_asrc_p8"
down_revision: str = "v2_mem_p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent",
        sa.Column("source", sa.String(8), server_default="v1", nullable=False),
    )
    op.create_index("ix_agent_source", "agent", ["source"])


def downgrade() -> None:
    op.drop_index("ix_agent_source", table_name="agent")
    op.drop_column("agent", "source")
