"""lead_reactivation_records: 180-day activation history for lead detail

Revision ID: lr02b3c4d5e6
Revises: ds01a2b3c4d5
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "lr02b3c4d5e6"
down_revision: Union[str, None] = "ds01a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_reactivation_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("lead_id", sa.String(36), nullable=False, index=True),
        sa.Column("original_lead_code", sa.String(50), nullable=True),
        sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("project_recent", sa.String(500), nullable=True),
        sa.Column("follow_progress", sa.String(500), nullable=True),
        sa.Column("site_visit", sa.String(500), nullable=True),
        sa.Column("report_project_status", sa.String(50), nullable=True),
        sa.Column("submitted_by_id", sa.String(36), nullable=True),
        sa.Column("submitted_by_name", sa.String(100), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_lead_reactivation_records_lead_round",
        "lead_reactivation_records",
        ["lead_id", "round_no"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_reactivation_records_lead_round", table_name="lead_reactivation_records")
    op.drop_table("lead_reactivation_records")
