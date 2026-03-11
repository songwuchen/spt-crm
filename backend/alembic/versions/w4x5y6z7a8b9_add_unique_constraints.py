"""add unique constraints on business keys and soft-delete composite indexes

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-03-11
"""
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def _index_exists(conn, table_name, index_name):
    insp = sa_inspect(conn)
    return any(idx["name"] == index_name for idx in insp.get_indexes(table_name))


def _constraint_exists(conn, table_name, constraint_name):
    insp = sa_inspect(conn)
    return any(uc["name"] == constraint_name for uc in insp.get_unique_constraints(table_name))


def upgrade() -> None:
    conn = op.get_bind()

    # --- Unique constraints on business keys (composite with tenant_id) ---
    pairs = [
        ("opportunity_projects", "uq_project_tenant_code", ["tenant_id", "project_code"]),
        ("quotes", "uq_quote_tenant_no", ["tenant_id", "quote_no"]),
        ("contracts", "uq_contract_tenant_no", ["tenant_id", "contract_no"]),
        ("invoices", "uq_invoice_tenant_no", ["tenant_id", "invoice_no"]),
        ("payment_plans", "uq_plan_tenant_no", ["tenant_id", "plan_no"]),
    ]
    for table, name, cols in pairs:
        try:
            if not _constraint_exists(conn, table, name):
                op.create_unique_constraint(name, table, cols)
        except Exception:
            pass  # table may not exist yet in fresh installs

    # --- Soft-delete composite indexes ---
    soft_delete_indexes = [
        ("customers", "ix_customer_tenant_deleted", ["tenant_id", "is_deleted"]),
        ("leads", "ix_lead_tenant_deleted", ["tenant_id", "is_deleted"]),
    ]
    for table, name, cols in soft_delete_indexes:
        try:
            if not _index_exists(conn, table, name):
                op.create_index(name, table, cols)
        except Exception:
            pass


def downgrade() -> None:
    pairs = [
        ("opportunity_projects", "uq_project_tenant_code"),
        ("quotes", "uq_quote_tenant_no"),
        ("contracts", "uq_contract_tenant_no"),
        ("invoices", "uq_invoice_tenant_no"),
        ("payment_plans", "uq_plan_tenant_no"),
    ]
    for table, name in pairs:
        try:
            op.drop_constraint(name, table)
        except Exception:
            pass

    for name in ["ix_customer_tenant_deleted", "ix_lead_tenant_deleted"]:
        try:
            op.drop_index(name)
        except Exception:
            pass
