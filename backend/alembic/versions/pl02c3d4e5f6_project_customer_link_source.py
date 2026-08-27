"""opportunity_projects: customer_link_source for lead convert customer binding

Revision ID: pl02c3d4e5f6
Revises: cu02b3c4d5e6
Create Date: 2026-08-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "pl02c3d4e5f6"
down_revision = "cu02b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("opportunity_projects")}
    if "customer_link_source" not in cols:
        op.add_column(
            "opportunity_projects",
            sa.Column("customer_link_source", sa.String(32), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("opportunity_projects")}
    if "customer_link_source" in cols:
        op.drop_column("opportunity_projects", "customer_link_source")
