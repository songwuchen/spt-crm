"""add orders and tenders tables

订单(orders) 与 标书(tenders) 独立领域，直接关联 customer_id 以支持客户报表。

Revision ID: e2f3a4b5c6d7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "e2f3a4b5c6d7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    if "orders" not in existing:
        op.create_table(
            "orders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("order_no", sa.String(64), nullable=False),
            sa.Column("customer_id", sa.String(36), nullable=False, index=True),
            sa.Column("project_id", sa.String(36), index=True),
            sa.Column("contract_id", sa.String(36), index=True),
            sa.Column("title", sa.String(300)),
            sa.Column("amount", sa.Numeric(18, 2)),
            sa.Column("currency", sa.String(8), default="CNY"),
            sa.Column("status", sa.String(16), default="draft"),
            sa.Column("order_date", sa.Date),
            sa.Column("delivery_date", sa.Date),
            sa.Column("owner_id", sa.String(36)),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("remark", sa.Text),
            sa.Column("is_deleted", sa.Boolean, default=False, index=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    if "tenders" not in existing:
        op.create_table(
            "tenders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("tender_no", sa.String(64), nullable=False),
            sa.Column("customer_id", sa.String(36), nullable=False, index=True),
            sa.Column("project_id", sa.String(36), index=True),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("bid_amount", sa.Numeric(18, 2)),
            sa.Column("budget_amount", sa.Numeric(18, 2)),
            sa.Column("status", sa.String(16), default="preparing"),
            sa.Column("submit_date", sa.Date),
            sa.Column("open_date", sa.Date),
            sa.Column("result", sa.String(300)),
            sa.Column("owner_id", sa.String(36)),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("remark", sa.Text),
            sa.Column("is_deleted", sa.Boolean, default=False, index=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()
    if "tenders" in existing:
        op.drop_table("tenders")
    if "orders" in existing:
        op.drop_table("orders")
