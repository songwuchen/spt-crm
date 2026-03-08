"""add mentions_json to activities

Revision ID: m4n5o6p7q8r9
Revises: k3c4d5e6f7a8
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "m4n5o6p7q8r9"
down_revision = "k3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("mentions_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "mentions_json")
