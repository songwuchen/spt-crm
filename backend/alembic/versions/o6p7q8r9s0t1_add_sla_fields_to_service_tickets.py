"""add sla fields to service tickets

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("service_tickets", sa.Column("sla_respond_by", sa.DateTime(timezone=True), nullable=True))
    op.add_column("service_tickets", sa.Column("sla_resolve_by", sa.DateTime(timezone=True), nullable=True))
    op.add_column("service_tickets", sa.Column("sla_responded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("service_tickets", sa.Column("sla_resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("service_tickets", "sla_resolved_at")
    op.drop_column("service_tickets", "sla_responded_at")
    op.drop_column("service_tickets", "sla_resolve_by")
    op.drop_column("service_tickets", "sla_respond_by")
