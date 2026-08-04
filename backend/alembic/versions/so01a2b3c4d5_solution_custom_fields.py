"""solutions.custom_fields_json for entity extension fields

Revision ID: so01a2b3c4d5
Revises: st01d2e3f4a5
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "so01a2b3c4d5"
down_revision = "st01d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "solutions" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("solutions")}
    if "custom_fields_json" not in cols:
        op.add_column("solutions", sa.Column("custom_fields_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "solutions" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("solutions")}
    if "custom_fields_json" in cols:
        op.drop_column("solutions", "custom_fields_json")
