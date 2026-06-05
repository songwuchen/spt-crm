"""add collection (debt transfer + follow-up) tables

应收清欠：清欠/责任移交单 debt_transfers（含抢单接收）、催收跟进 collection_followups。
应收账龄为实时计算，无需建表。

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "a4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    if "debt_transfers" not in existing:
        op.create_table(
            "debt_transfers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("transfer_no", sa.String(64), nullable=False),
            sa.Column("customer_id", sa.String(36), index=True),
            sa.Column("customer_name", sa.String(300)),
            sa.Column("transfer_type", sa.String(32), default="sales_to_collection"),
            sa.Column("from_department_id", sa.String(36)),
            sa.Column("from_department_name", sa.String(100)),
            sa.Column("from_owner_id", sa.String(36)),
            sa.Column("from_owner_name", sa.String(100)),
            sa.Column("to_department_id", sa.String(36), index=True),
            sa.Column("to_department_name", sa.String(100)),
            sa.Column("debt_amount", sa.Numeric(18, 2)),
            sa.Column("contact", sa.String(100)),
            sa.Column("contact_phone", sa.String(64)),
            sa.Column("debt_note", sa.Text),
            sa.Column("reason", sa.Text),
            sa.Column("deadline", sa.Date),
            sa.Column("assess_date", sa.Date),
            sa.Column("commitment", sa.Text),
            sa.Column("status", sa.String(16), default="pending"),
            sa.Column("claimed_by_id", sa.String(36)),
            sa.Column("claimed_by_name", sa.String(100)),
            sa.Column("claimed_department_id", sa.String(36)),
            sa.Column("claimed_department_name", sa.String(100)),
            sa.Column("claimed_at", sa.DateTime(timezone=True)),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_debt_transfer_tenant_status", "debt_transfers", ["tenant_id", "status"])

    if "collection_followups" not in existing:
        op.create_table(
            "collection_followups",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("customer_id", sa.String(36), index=True),
            sa.Column("customer_name", sa.String(300)),
            sa.Column("transfer_id", sa.String(36), index=True),
            sa.Column("follow_date", sa.Date),
            sa.Column("method", sa.String(32)),
            sa.Column("feedback", sa.Text),
            sa.Column("expected_date", sa.Date),
            sa.Column("amount_promised", sa.Numeric(18, 2)),
            sa.Column("next_action", sa.Text),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()
    for t in ("collection_followups", "debt_transfers"):
        if t in existing:
            op.drop_table(t)
