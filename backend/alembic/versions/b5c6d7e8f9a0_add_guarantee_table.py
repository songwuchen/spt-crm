"""add guarantee (保函/保证金) table

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    if "guarantees" not in existing:
        op.create_table(
            "guarantees",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("guarantee_no", sa.String(64), nullable=False),
            sa.Column("type", sa.String(24), default="performance"),
            sa.Column("direction", sa.String(16), default="outgoing"),
            sa.Column("contract_id", sa.String(36), index=True),
            sa.Column("project_id", sa.String(36), index=True),
            sa.Column("customer_id", sa.String(36), index=True),
            sa.Column("customer_name", sa.String(300)),
            sa.Column("amount", sa.Numeric(18, 2)),
            sa.Column("issuer", sa.String(200)),
            sa.Column("fee", sa.Numeric(18, 2)),
            sa.Column("rate", sa.Numeric(8, 4)),
            sa.Column("effective_date", sa.Date),
            sa.Column("expiry_date", sa.Date, index=True),
            sa.Column("return_date", sa.Date),
            sa.Column("status", sa.String(16), default="active"),
            sa.Column("owner_id", sa.String(36)),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("remark", sa.Text),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_guarantee_tenant_status", "guarantees", ["tenant_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "guarantees" in sa_inspect(bind).get_table_names():
        op.drop_table("guarantees")
