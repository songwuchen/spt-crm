"""add lead intel review fields (customer_newness / review_opinion)

情报审批：新/老客户、操作意见；review_status 扩展 attacked（袭击）由应用层写入，列类型不变。

Revision ID: ir01c2d3e4f5
Revises: rp02b3c4d5e6
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ir01c2d3e4f5"
down_revision = "rp02b3c4d5e6"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "leads" not in insp.get_table_names():
        return
    if not _has_column(insp, "leads", "customer_newness"):
        op.add_column("leads", sa.Column("customer_newness", sa.String(10), nullable=True))
    if not _has_column(insp, "leads", "review_opinion"):
        op.add_column("leads", sa.Column("review_opinion", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "leads", "review_opinion"):
        op.drop_column("leads", "review_opinion")
    if _has_column(insp, "leads", "customer_newness"):
        op.drop_column("leads", "customer_newness")
