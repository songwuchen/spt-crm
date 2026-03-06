"""add activity follow fields

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f7
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activities", sa.Column("next_follow_date", sa.Date(), nullable=True))
    op.add_column("activities", sa.Column("biz_name", sa.String(200), nullable=True))


def downgrade():
    op.drop_column("activities", "biz_name")
    op.drop_column("activities", "next_follow_date")
