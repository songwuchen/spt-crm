"""add reported_at to leads

线索「报备时间」：新建默认当前时间，用户可改；历史数据回填 created_at。

Revision ID: rp02b3c4d5e6
Revises: rp01a2b3c4d5
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "rp02b3c4d5e6"
down_revision = "rp01a2b3c4d5"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if not _has_column(insp, "leads", "reported_at"):
        op.add_column("leads", sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_leads_reported_at", "leads", ["reported_at"])
    op.execute("UPDATE leads SET reported_at = created_at WHERE reported_at IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "leads", "reported_at"):
        op.drop_index("ix_leads_reported_at", table_name="leads")
        op.drop_column("leads", "reported_at")
