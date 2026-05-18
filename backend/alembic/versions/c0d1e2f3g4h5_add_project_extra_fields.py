"""add extra fields to opportunity_projects (issue #18)

Adds business-specific booleans (保函/重量要求/呆滞设备) and payment_method.
Attachment support is already available via attachment_links biz_type='project'.

Revision ID: c0d1e2f3g4h5
Revises: b9c0d1e2f3g4
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa


revision = "c0d1e2f3g4h5"
down_revision = "b9c0d1e2f3g4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunity_projects", sa.Column("has_guarantee", sa.Boolean(), nullable=True))
    op.add_column("opportunity_projects", sa.Column("has_weight_requirement", sa.Boolean(), nullable=True))
    op.add_column("opportunity_projects", sa.Column("uses_idle_equipment", sa.Boolean(), nullable=True))
    op.add_column("opportunity_projects", sa.Column("payment_method", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunity_projects", "payment_method")
    op.drop_column("opportunity_projects", "uses_idle_equipment")
    op.drop_column("opportunity_projects", "has_weight_requirement")
    op.drop_column("opportunity_projects", "has_guarantee")
