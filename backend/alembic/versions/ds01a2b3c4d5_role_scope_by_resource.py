"""roles.scope_by_resource: per-module data scope overrides

Revision ID: ds01a2b3c4d5
Revises: pl01a2b3c4d5
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ds01a2b3c4d5"
down_revision = "pl01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("roles")}
    if "scope_by_resource" not in cols:
        op.add_column(
            "roles",
            sa.Column("scope_by_resource", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("roles")}
    if "scope_by_resource" in cols:
        op.drop_column("roles", "scope_by_resource")
