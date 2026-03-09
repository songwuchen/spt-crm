"""add reports_to_id to contacts

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns("contacts")]
    if "reports_to_id" not in columns:
        op.add_column("contacts", sa.Column("reports_to_id", sa.String(36), nullable=True))


def downgrade():
    op.drop_column("contacts", "reports_to_id")
