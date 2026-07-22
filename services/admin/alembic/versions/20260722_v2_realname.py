"""V2.0 用户实名字段（M2.6：三要素 API，注册即实名）

Revision ID: v2_real_p4
Revises: v2_act_p3
Create Date: 2026-07-22

users 加 real_name / id_card_hash（SHA256，不存明文）/ realname_status（unverified/verified）。
"""
import sqlalchemy as sa
from alembic import op

revision: str = "v2_real_p4"
down_revision: str = "v2_act_p3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("real_name", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("id_card_hash", sa.String(64), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "realname_status",
            sa.String(16),
            server_default="unverified",
            nullable=False,
        ),
    )
    op.create_index("ix_users_realname_status", "users", ["realname_status"])


def downgrade() -> None:
    op.drop_index("ix_users_realname_status", table_name="users")
    op.drop_column("users", "realname_status")
    op.drop_column("users", "id_card_hash")
    op.drop_column("users", "real_name")
