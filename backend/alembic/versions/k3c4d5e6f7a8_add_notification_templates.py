"""add notification_templates table

Revision ID: k3c4d5e6f7a8
Revises: j2b3c4d5e6f7
Create Date: 2026-03-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "k3c4d5e6f7a8"
down_revision = "j2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("title_template", sa.String(500), nullable=False),
        sa.Column("content_template", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_deleted", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table("notification_templates")
