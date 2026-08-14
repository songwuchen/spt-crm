"""opportunity_projects: lead_id / lead_code for source lead on convert

Revision ID: pl01a2b3c4d5
Revises: um01a2b3c4d5
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "pl01a2b3c4d5"
down_revision = "um01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("opportunity_projects")}
    if "lead_id" not in cols:
        op.add_column(
            "opportunity_projects",
            sa.Column("lead_id", sa.String(36), nullable=True),
        )
        op.create_index(
            "ix_opportunity_projects_lead_id",
            "opportunity_projects",
            ["lead_id"],
        )
    if "lead_code" not in cols:
        op.add_column(
            "opportunity_projects",
            sa.Column("lead_code", sa.String(64), nullable=True),
        )
        op.create_index(
            "ix_opportunity_projects_lead_code",
            "opportunity_projects",
            ["tenant_id", "lead_code"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("opportunity_projects")}
    indexes = {i["name"] for i in insp.get_indexes("opportunity_projects")}
    if "ix_opportunity_projects_lead_code" in indexes:
        op.drop_index("ix_opportunity_projects_lead_code", table_name="opportunity_projects")
    if "ix_opportunity_projects_lead_id" in indexes:
        op.drop_index("ix_opportunity_projects_lead_id", table_name="opportunity_projects")
    if "lead_code" in cols:
        op.drop_column("opportunity_projects", "lead_code")
    if "lead_id" in cols:
        op.drop_column("opportunity_projects", "lead_id")
