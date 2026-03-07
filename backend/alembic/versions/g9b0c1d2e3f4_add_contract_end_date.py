"""add contract end_date

Revision ID: g9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "g9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("contracts", "end_date")
