"""add activity contact_id

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activities", sa.Column("contact_id", sa.String(36), nullable=True))
    op.create_index("ix_activities_contact_id", "activities", ["contact_id"])


def downgrade():
    op.drop_index("ix_activities_contact_id", "activities")
    op.drop_column("activities", "contact_id")
