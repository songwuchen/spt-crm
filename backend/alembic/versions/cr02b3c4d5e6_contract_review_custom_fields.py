"""contract_reviews.custom_fields_json for entity extension fields

Revision ID: cr02b3c4d5e6
Revises: cr01a2b3c4d5
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "cr02b3c4d5e6"
down_revision = "cr01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "contract_reviews" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("contract_reviews")}
    if "custom_fields_json" not in cols:
        op.add_column("contract_reviews", sa.Column("custom_fields_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "contract_reviews" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("contract_reviews")}
    if "custom_fields_json" in cols:
        op.drop_column("contract_reviews", "custom_fields_json")
