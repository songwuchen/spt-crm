"""add soft delete to service_tickets

售后工单删除改为软删，与线索/客户一致，避免误删不可恢复。

Revision ID: st01d2e3f4a5
Revises: cr02b3c4d5e6
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "st01d2e3f4a5"
down_revision = "cr02b3c4d5e6"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "service_tickets" not in insp.get_table_names():
        return
    if not _has_column(insp, "service_tickets", "is_deleted"):
        op.add_column(
            "service_tickets",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.create_index("ix_service_tickets_is_deleted", "service_tickets", ["is_deleted"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "service_tickets", "is_deleted"):
        if "ix_service_tickets_is_deleted" in {i["name"] for i in insp.get_indexes("service_tickets")}:
            op.drop_index("ix_service_tickets_is_deleted", "service_tickets")
        op.drop_column("service_tickets", "is_deleted")
