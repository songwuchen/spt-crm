"""contracts.external_key + allow duplicate contract_no for JDY 1:1 sync

Revision ID: ct05e6f7a8b9
Revises: ct04d5e6f7a8
Create Date: 2026-08-26

简道云合同登记按 data_id 一条对应 CRM 一行；同合同号的「新增/变动」允许多行。
- 新增 external_key（租户内唯一，可空）
- 去掉 uq_contract_tenant_no（页面建单仍由业务层校验合同号唯一）
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ct05e6f7a8b9"
down_revision = "ct04d5e6f7a8"
branch_labels = None
depends_on = None


def _index_exists(conn, table: str, name: str) -> bool:
    return any(idx["name"] == name for idx in sa_inspect(conn).get_indexes(table))


def _constraint_exists(conn, table: str, name: str) -> bool:
    return any(uc["name"] == name for uc in sa_inspect(conn).get_unique_constraints(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("contracts")}
    if "external_key" not in cols:
        op.add_column("contracts", sa.Column("external_key", sa.String(128), nullable=True))

    if _constraint_exists(bind, "contracts", "uq_contract_tenant_no"):
        op.drop_constraint("uq_contract_tenant_no", "contracts", type_="unique")

    if not _index_exists(bind, "contracts", "uq_contracts_tenant_external_key"):
        op.create_index(
            "uq_contracts_tenant_external_key",
            "contracts",
            ["tenant_id", "external_key"],
            unique=True,
            postgresql_where=sa.text("external_key IS NOT NULL"),
            sqlite_where=sa.text("external_key IS NOT NULL"),
        )
    if not _index_exists(bind, "contracts", "ix_contracts_external_key"):
        op.create_index("ix_contracts_external_key", "contracts", ["external_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "contracts", "ix_contracts_external_key"):
        op.drop_index("ix_contracts_external_key", table_name="contracts")
    if _index_exists(bind, "contracts", "uq_contracts_tenant_external_key"):
        op.drop_index("uq_contracts_tenant_external_key", table_name="contracts")

    # Re-dedupe before restoring unique contract_no
    from sqlalchemy import text
    bind.execute(text("""
        DELETE FROM contracts WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, contract_no ORDER BY created_at DESC
                ) AS rn FROM contracts
            ) sub WHERE rn > 1
        )
    """))
    if not _constraint_exists(bind, "contracts", "uq_contract_tenant_no"):
        op.create_unique_constraint("uq_contract_tenant_no", "contracts", ["tenant_id", "contract_no"])

    cols = {c["name"] for c in sa_inspect(bind).get_columns("contracts")}
    if "external_key" in cols:
        op.drop_column("contracts", "external_key")
