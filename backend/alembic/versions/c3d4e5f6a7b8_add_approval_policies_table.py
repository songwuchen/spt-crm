"""add approval_policies table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-01 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("biz_type", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(200)),
        sa.Column("condition_json", sa.JSON),
        sa.Column("approver_rules_json", sa.JSON),
        sa.Column("approval_mode", sa.String(32), server_default="sequential"),
        sa.Column("sla_hours", sa.Integer),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("approval_policies")
