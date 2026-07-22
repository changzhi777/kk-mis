"""V2.0 经销商主体资质表（M1.5：approve 后后台补充 + 平台核验）

Revision ID: v2_dealer_q2
Revises: v2_dealer_p1
Create Date: 2026-07-22

新建 v2_dealer_qualification：营业执照/法人/统一社会信用代码 + 核验状态。
"""
from alembic import op
import sqlalchemy as sa

revision: str = "v2_dealer_q2"
down_revision: str = "v2_dealer_p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_dealer_qualification",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("agent_id", sa.BigInteger, sa.ForeignKey("agent.id"), nullable=False),
        sa.Column("company_name", sa.String(100), nullable=False),
        sa.Column("legal_person", sa.String(50)),
        sa.Column("business_license_no", sa.String(32)),
        sa.Column("business_license_url", sa.String(255)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("verified_by", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime),
        sa.Column("reject_reason", sa.String(200)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index(
        "ix_v2_dealer_qualification_agent_id", "v2_dealer_qualification", ["agent_id"]
    )
    op.create_index(
        "ix_v2_dealer_qualification_business_license_no",
        "v2_dealer_qualification",
        ["business_license_no"],
    )
    op.create_index(
        "ix_v2_dealer_qualification_status", "v2_dealer_qualification", ["status"]
    )


def downgrade() -> None:
    op.drop_table("v2_dealer_qualification")
