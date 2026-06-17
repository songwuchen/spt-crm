"""add contract open-api write fields

Contracts ingested via the Open API (e.g. 简道云 合同登记表) are customer-centric and
may have no CRM project. Add a direct customer_id link + custom_fields_json (tenant
extension fields), and relax project_id to nullable.

Revision ID: c7a1f2b3d4e5
Revises: f9a0b1c2d3e4
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "c7a1f2b3d4e5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    indexes = {i["name"] for i in inspector.get_indexes("contracts")}

    if "customer_id" not in cols:
        op.add_column("contracts", sa.Column("customer_id", sa.String(36), nullable=True))
    if "ix_contracts_customer_id" not in indexes:
        op.create_index("ix_contracts_customer_id", "contracts", ["customer_id"])
    if "custom_fields_json" not in cols:
        op.add_column("contracts", sa.Column("custom_fields_json", sa.JSON(), nullable=True))

    # Relax project_id: contracts created through the Open API may have no project.
    op.alter_column("contracts", "project_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    indexes = {i["name"] for i in inspector.get_indexes("contracts")}

    # Best-effort restore of NOT NULL (only safe if no null rows exist).
    op.alter_column("contracts", "project_id", existing_type=sa.String(36), nullable=False)
    if "custom_fields_json" in cols:
        op.drop_column("contracts", "custom_fields_json")
    if "ix_contracts_customer_id" in indexes:
        op.drop_index("ix_contracts_customer_id", table_name="contracts")
    if "customer_id" in cols:
        op.drop_column("contracts", "customer_id")
