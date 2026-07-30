"""add contract registration alignment fields

Align SPT-CRM contracts with 简道云「合同登记表」P0 fields:
drawing_no, peer_contract_no, acquire_method, delivery_date, change_type.

Revision ID: ct01a2b3c4d5
Revises: ct03c4d5e6f7
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ct01a2b3c4d5"
down_revision = "ct03c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    indexes = {i["name"] for i in inspector.get_indexes("contracts")}

    if "drawing_no" not in cols:
        op.add_column("contracts", sa.Column("drawing_no", sa.String(100), nullable=True))
    if "ix_contracts_drawing_no" not in indexes:
        op.create_index("ix_contracts_drawing_no", "contracts", ["drawing_no"])
    if "peer_contract_no" not in cols:
        op.add_column("contracts", sa.Column("peer_contract_no", sa.String(100), nullable=True))
    if "acquire_method" not in cols:
        op.add_column("contracts", sa.Column("acquire_method", sa.String(64), nullable=True))
    if "delivery_date" not in cols:
        op.add_column("contracts", sa.Column("delivery_date", sa.Date(), nullable=True))
    if "change_type" not in cols:
        op.add_column("contracts", sa.Column("change_type", sa.String(16), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    indexes = {i["name"] for i in inspector.get_indexes("contracts")}
    if "ix_contracts_drawing_no" in indexes:
        op.drop_index("ix_contracts_drawing_no", table_name="contracts")
    for col in ("change_type", "delivery_date", "acquire_method", "peer_contract_no", "drawing_no"):
        if col in cols:
            op.drop_column("contracts", col)
