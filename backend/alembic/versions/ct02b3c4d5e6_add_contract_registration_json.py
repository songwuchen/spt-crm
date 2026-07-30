"""add contract registration_json and order/card dates

Stores 简道云合同登记业务扩展字段 in registration_json, plus order_date/card_date.

Revision ID: ct02b3c4d5e6
Revises: ct01a2b3c4d5
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ct02b3c4d5e6"
down_revision = "ct01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}

    if "order_date" not in cols:
        op.add_column("contracts", sa.Column("order_date", sa.Date(), nullable=True))
    if "card_date" not in cols:
        op.add_column("contracts", sa.Column("card_date", sa.Date(), nullable=True))
    if "registration_json" not in cols:
        op.add_column("contracts", sa.Column("registration_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    for col in ("registration_json", "card_date", "order_date"):
        if col in cols:
            op.drop_column("contracts", col)
