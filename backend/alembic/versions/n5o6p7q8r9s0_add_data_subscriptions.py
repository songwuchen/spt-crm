"""add data_subscriptions table

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("biz_type", sa.String(64), nullable=False),
        sa.Column("biz_id", sa.String(36), nullable=False),
        sa.Column("biz_name", sa.String(200)),
        sa.Column("events_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_data_subscriptions_biz", "data_subscriptions", ["biz_type", "biz_id"])


def downgrade() -> None:
    op.drop_index("ix_data_subscriptions_biz", table_name="data_subscriptions")
    op.drop_table("data_subscriptions")
