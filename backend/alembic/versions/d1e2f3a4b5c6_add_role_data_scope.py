"""add role data_scope

Adds roles.data_scope for role-configurable data permission:
- self (default/NULL): user only sees records they own
- dept: user sees records owned by anyone in their department sub-tree (incl. descendants)
- all: user sees all tenant data

Revision ID: d1e2f3a4b5c6
Revises: c7a1f2b3d4e5
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d1e2f3a4b5c6"
down_revision = "c7a1f2b3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa_inspect(bind).get_columns("roles")}
    if "data_scope" not in cols:
        op.add_column("roles", sa.Column("data_scope", sa.String(16), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa_inspect(bind).get_columns("roles")}
    if "data_scope" in cols:
        op.drop_column("roles", "data_scope")
