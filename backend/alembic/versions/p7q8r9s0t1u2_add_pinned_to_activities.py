"""add pinned to activities

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activities", sa.Column("pinned", sa.Boolean(), nullable=True, server_default="false"))


def downgrade():
    op.drop_column("activities", "pinned")
