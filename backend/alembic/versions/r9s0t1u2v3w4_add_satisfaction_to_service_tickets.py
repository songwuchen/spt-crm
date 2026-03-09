"""add satisfaction to service tickets

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns("service_tickets")]
    if "satisfaction_score" not in columns:
        op.add_column("service_tickets", sa.Column("satisfaction_score", sa.Integer(), nullable=True))
    if "satisfaction_comment" not in columns:
        op.add_column("service_tickets", sa.Column("satisfaction_comment", sa.Text(), nullable=True))
    if "satisfaction_at" not in columns:
        op.add_column("service_tickets", sa.Column("satisfaction_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("service_tickets", "satisfaction_at")
    op.drop_column("service_tickets", "satisfaction_comment")
    op.drop_column("service_tickets", "satisfaction_score")
