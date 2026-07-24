"""add reporter_id / reporter_name to leads

线索「报备人」：与录入人(created_by)、负责人(owner)区分。
新建表单可选，默认当前用户；历史数据回填为录入人。

Revision ID: rp01a2b3c4d5
Revises: pw01a2b3c4d5
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "rp01a2b3c4d5"
down_revision = "pw01a2b3c4d5"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if not _has_column(insp, "leads", "reporter_id"):
        op.add_column("leads", sa.Column("reporter_id", sa.String(36), nullable=True))
        op.create_index("ix_leads_reporter_id", "leads", ["reporter_id"])
    if not _has_column(insp, "leads", "reporter_name"):
        op.add_column("leads", sa.Column("reporter_name", sa.String(100), nullable=True))
    # 历史：无报备人时用录入人回填（再退到负责人）
    op.execute(
        "UPDATE leads SET "
        "reporter_id = COALESCE(created_by_id, owner_id), "
        "reporter_name = COALESCE(created_by_name, owner_name) "
        "WHERE reporter_id IS NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "leads", "reporter_name"):
        op.drop_column("leads", "reporter_name")
    if _has_column(insp, "leads", "reporter_id"):
        op.drop_index("ix_leads_reporter_id", table_name="leads")
        op.drop_column("leads", "reporter_id")
