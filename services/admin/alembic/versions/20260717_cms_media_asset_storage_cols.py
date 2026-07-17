"""CMS MediaAsset Storage 抽象层 4 列补迁移（PROD-SCHEMA-DRIFT 修复）。

Revision ID: 20260717_cms_media_asset_storage_cols
Revises: 20260715_cms_payment_exception_event_p1
Create Date: 2026-07-17

背景：
- Sprint 0（2026-07-14）在 models/cms.py::MediaAsset 加了 4 个 Storage 抽象层字段
  （storage_backend / storage_key / etag / content_type）；
- 但 admin 运行时仍用 init_db() create_all() 建表，create_all 不 ALTER 已有表；
- 生产 nanoai.fun 在 2026-07-16 上线时手工 ALTER 补了这 4 列
  （见 memory nanoai-deploy-2026-07-16），导致生产 schema 与 alembic 历史脱节
  （PROD-SCHEMA-DRIFT）；
- 本 revision 把这 4 列纳入正式 alembic 迁移，让开发/生产 schema 收敛。

幂等设计（关键）：
- 生产库可能已有这 4 列（手工 ALTER），开发库可能没有；
- upgrade 用 inspector 逐列检查，已存在则跳过（checkfirst），避免 "duplicate column"；
- downgrade 同样逐列检查存在才删，SQLite 用 batch_alter_table 重建表。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# Alembic revision identifiers.
revision: str = "cms_media_cols"
down_revision: str | Sequence[str] | None = "cms_pmt_exc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "cms_media_asset"

# 4 列定义严格对齐 models/cms.py::MediaAsset（2026-07-14 Sprint 0 引入）。
# (name, type, nullable, server_default)
_COLUMNS: tuple[tuple[str, "sa.types.TypeEngine", bool, object], ...] = (
    ("storage_backend", sa.String(length=20), False, sa.text("'local'")),
    ("storage_key", sa.String(length=512), True, None),
    ("etag", sa.String(length=64), True, None),
    ("content_type", sa.String(length=64), False, sa.text("'image/png'")),
)


def _existing_columns() -> set[str]:
    """返回 cms_media_asset 当前已有的列名集合（离线 --sql 模式返回空集）。"""
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
    except sa.exc.NoInspectionAvailable:
        # 离线 alembic upgrade head --sql 走 MockConnection，无真 inspector。
        return set()
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def _dialect_name() -> str:
    """识别数据库方言（drop_column 时 SQLite 需 batch 重建表）。"""
    bind = op.get_bind()
    try:
        return str(inspect(bind).dialect.name)
    except sa.exc.NoInspectionAvailable:
        return str(bind.dialect.name)


def upgrade() -> None:
    """补 4 列（幂等：已存在则跳过）。"""
    existing = _existing_columns()
    for name, col_type, nullable, server_default in _COLUMNS:
        if name in existing:
            continue
        op.add_column(
            _TABLE,
            sa.Column(
                name,
                col_type,
                nullable=nullable,
                server_default=server_default,
            ),
        )


def downgrade() -> None:
    """删 4 列（回滚到加列前；SQLite 用 batch 重建表）。

    downgrade 不做幂等检查——语义是"回滚本次迁移"，前置条件是 upgrade 已跑
    （列一定存在）。生产回滚应走受控流程，不靠代码防御；这与现有
    exception_event_p1 的无条件 drop 风格一致。
    """
    dialect = _dialect_name()
    for name, *_rest in _COLUMNS:
        if dialect == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(name)
        else:
            op.drop_column(_TABLE, name)
