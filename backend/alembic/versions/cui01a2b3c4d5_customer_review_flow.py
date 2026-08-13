"""customers: review_status / review_flow_id / reject_reason / need_info_distribute

Revision ID: cui01a2b3c4d5
Revises: lr01a2b3c4d5
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "cui01a2b3c4d5"
down_revision = "lr01a2b3c4d5"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("review_status", sa.Column("review_status", sa.String(20), nullable=False, server_default="approved")),
    ("review_flow_id", sa.Column("review_flow_id", sa.String(36), nullable=True)),
    ("reject_reason", sa.Column("reject_reason", sa.Text(), nullable=True)),
    ("need_info_distribute", sa.Column("need_info_distribute", sa.Boolean(), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    existing = {c["name"] for c in insp.get_columns("customers")}
    for name, col in _COLUMNS:
        if name not in existing:
            op.add_column("customers", col)
    # 存量客户视为已通过，避免强制重审
    op.execute(sa.text("UPDATE customers SET review_status = 'approved' WHERE review_status IS NULL OR review_status = ''"))
    indexes = {i["name"] for i in insp.get_indexes("customers")}
    if "ix_customers_review_status" not in indexes:
        op.create_index("ix_customers_review_status", "customers", ["review_status"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    indexes = {i["name"] for i in insp.get_indexes("customers")}
    if "ix_customers_review_status" in indexes:
        op.drop_index("ix_customers_review_status", table_name="customers")
    existing = {c["name"] for c in insp.get_columns("customers")}
    for name, _ in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("customers", name)
