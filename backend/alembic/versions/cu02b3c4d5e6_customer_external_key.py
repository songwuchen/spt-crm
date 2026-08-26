"""customers.external_key for JDY 1:1 sync (even without customer_code)

Revision ID: cu02b3c4d5e6
Revises: ct05e6f7a8b9
Create Date: 2026-08-26

简道云客户登记大量无客户编号；仅靠 customer_code upsert 会导致每次全量同步重复建档。
按 data_id -> external_key 一条登记对应一行。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "cu02b3c4d5e6"
down_revision = "ct05e6f7a8b9"
branch_labels = None
depends_on = None


def _index_exists(conn, table: str, name: str) -> bool:
    return any(idx["name"] == name for idx in sa_inspect(conn).get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("customers")}
    if "external_key" not in cols:
        op.add_column("customers", sa.Column("external_key", sa.String(128), nullable=True))

    if not _index_exists(bind, "customers", "uq_customers_tenant_external_key"):
        op.create_index(
            "uq_customers_tenant_external_key",
            "customers",
            ["tenant_id", "external_key"],
            unique=True,
            postgresql_where=sa.text("external_key IS NOT NULL"),
            sqlite_where=sa.text("external_key IS NOT NULL"),
        )
    if not _index_exists(bind, "customers", "ix_customers_external_key"):
        op.create_index("ix_customers_external_key", "customers", ["external_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "customers", "ix_customers_external_key"):
        op.drop_index("ix_customers_external_key", table_name="customers")
    if _index_exists(bind, "customers", "uq_customers_tenant_external_key"):
        op.drop_index("uq_customers_tenant_external_key", table_name="customers")
    cols = {c["name"] for c in sa_inspect(bind).get_columns("customers")}
    if "external_key" in cols:
        op.drop_column("customers", "external_key")