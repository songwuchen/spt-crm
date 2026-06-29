"""add customers/leads created_by_id / created_by_name

数据范围「本人」需涵盖「本人创建」的数据（issue #71）：客户/线索此前仅有负责人
(owner)，无录入人(created_by)，故负责人被改派后创建人即丢失可见性。新增录入人列
并回填历史数据（历史记录的负责人即录入人）。

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def _add_created_by(table: str) -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns(table)}
    if "created_by_id" not in cols:
        op.add_column(table, sa.Column("created_by_id", sa.String(36), nullable=True))
    if "created_by_name" not in cols:
        op.add_column(table, sa.Column("created_by_name", sa.String(100), nullable=True))
    # 回填：历史记录的负责人即为录入人
    op.execute(
        f"UPDATE {table} "
        "SET created_by_id = owner_id, created_by_name = owner_name "
        "WHERE created_by_id IS NULL"
    )


def _drop_created_by(table: str) -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns(table)}
    if "created_by_name" in cols:
        op.drop_column(table, "created_by_name")
    if "created_by_id" in cols:
        op.drop_column(table, "created_by_id")


def upgrade() -> None:
    _add_created_by("customers")
    _add_created_by("leads")


def downgrade() -> None:
    _drop_created_by("leads")
    _drop_created_by("customers")
