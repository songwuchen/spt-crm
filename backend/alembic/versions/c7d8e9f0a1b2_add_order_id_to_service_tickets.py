"""add service_tickets.order_id (售后工单关联客户订单)

售后工单可直接关联客户订单，以便快速获取产品信息（产品名称/规格/数量）。

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("service_tickets")}
    if "order_id" not in cols:
        op.add_column("service_tickets", sa.Column("order_id", sa.String(36), nullable=True))
    idx = {i["name"] for i in insp.get_indexes("service_tickets")}
    if "ix_service_tickets_order_id" not in idx:
        op.create_index("ix_service_tickets_order_id", "service_tickets", ["order_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    idx = {i["name"] for i in insp.get_indexes("service_tickets")}
    if "ix_service_tickets_order_id" in idx:
        op.drop_index("ix_service_tickets_order_id", table_name="service_tickets")
    cols = {c["name"] for c in insp.get_columns("service_tickets")}
    if "order_id" in cols:
        op.drop_column("service_tickets", "order_id")
