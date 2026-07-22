"""V2.0 经销商域（B2B 经销商预付激活模型，M1.1 数据底座）

Revision ID: v2_dealer_p1
Revises: cms_media_cols
Create Date: 2026-07-21 19:30:00

新建 4 表（v2_ 前缀，与 kk-mis 业务隔离）：
  v2_dealer_application  经销商申请
  v2_dealer_contract     经销商合同（服务费率/阶梯返点档占位，待合同阶段）
  v2_dealer_balance      经销商预付余额（一经销商一余额）
  v2_dealer_recharge     经销商充值记录（微信/支付宝 C 端 / 转账）

详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
  + .zcf/plan/current/v2-app-redesign.md
"""
from alembic import op
import sqlalchemy as sa

# Alembic revision identifiers.
revision: str = "v2_dealer_p1"
down_revision: str = "cms_media_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # v2_dealer_application
    op.create_table(
        "v2_dealer_application",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("province_code", sa.String(16), nullable=False),
        sa.Column("channel_note", sa.String(100)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime),
        sa.Column("reject_reason", sa.String(200)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_v2_dealer_application_user_id", "v2_dealer_application", ["user_id"])
    op.create_index(
        "ix_v2_dealer_application_province_code", "v2_dealer_application", ["province_code"]
    )
    op.create_index("ix_v2_dealer_application_status", "v2_dealer_application", ["status"])

    # v2_dealer_contract
    op.create_table(
        "v2_dealer_contract",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("agent_id", sa.BigInteger, sa.ForeignKey("agent.id"), nullable=False),
        sa.Column("start_date", sa.DateTime, nullable=False),
        sa.Column("end_date", sa.DateTime, nullable=False),
        sa.Column("service_fee_mode", sa.String(16), server_default="per_unit"),
        sa.Column("service_fee_rate", sa.Numeric(8, 4)),
        sa.Column("rebate_tiers", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("signed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_v2_dealer_contract_agent_id", "v2_dealer_contract", ["agent_id"])
    op.create_index("ix_v2_dealer_contract_status", "v2_dealer_contract", ["status"])

    # v2_dealer_balance（一经销商一余额）
    op.create_table(
        "v2_dealer_balance",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("agent_id", sa.BigInteger, sa.ForeignKey("agent.id"), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("frozen", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_recharged", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_consumed", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime),
        sa.UniqueConstraint("agent_id", name="uq_v2_dealer_balance_agent"),
    )

    # v2_dealer_recharge
    op.create_table(
        "v2_dealer_recharge",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("agent_id", sa.BigInteger, sa.ForeignKey("agent.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("txn_id", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime),
        sa.Column("paid_at", sa.DateTime),
        sa.Column("remark", sa.String(200)),
    )
    op.create_index("ix_v2_dealer_recharge_agent_id", "v2_dealer_recharge", ["agent_id"])
    op.create_index("ix_v2_dealer_recharge_txn_id", "v2_dealer_recharge", ["txn_id"])
    op.create_index("ix_v2_dealer_recharge_status", "v2_dealer_recharge", ["status"])


def downgrade() -> None:
    op.drop_table("v2_dealer_recharge")
    op.drop_table("v2_dealer_balance")
    op.drop_table("v2_dealer_contract")
    op.drop_table("v2_dealer_application")
