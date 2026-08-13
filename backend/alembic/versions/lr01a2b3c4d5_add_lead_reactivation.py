"""add lead 180-day reactivation fields

Revision ID: lr01a2b3c4d5
Revises: ld01a2b3c4d5
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "lr01a2b3c4d5"
down_revision: Union[str, None] = "ld01a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("cycle_anchor_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "leads",
        sa.Column("reactivation_status", sa.String(20), nullable=False, server_default="none"),
    )
    op.add_column("leads", sa.Column("reactivation_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "leads",
        sa.Column("reactivation_round", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_leads_cycle_anchor_at", "leads", ["cycle_anchor_at"])
    op.create_index("ix_leads_reactivation_status", "leads", ["reactivation_status"])


def downgrade() -> None:
    op.drop_index("ix_leads_reactivation_status", table_name="leads")
    op.drop_index("ix_leads_cycle_anchor_at", table_name="leads")
    op.drop_column("leads", "reactivation_round")
    op.drop_column("leads", "reactivation_notified_at")
    op.drop_column("leads", "reactivation_status")
    op.drop_column("leads", "cycle_anchor_at")
