"""add user tasks

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("priority", sa.String(16), default="normal"),
        sa.Column("status", sa.String(16), default="todo"),
        sa.Column("assignee_id", sa.String(36), nullable=False, index=True),
        sa.Column("assignee_name", sa.String(100), nullable=True),
        sa.Column("created_by_id", sa.String(36), nullable=True),
        sa.Column("created_by_name", sa.String(100), nullable=True),
        sa.Column("biz_type", sa.String(64), nullable=True),
        sa.Column("biz_id", sa.String(36), nullable=True),
        sa.Column("biz_name", sa.String(200), nullable=True),
        sa.Column("is_completed", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("user_tasks")
