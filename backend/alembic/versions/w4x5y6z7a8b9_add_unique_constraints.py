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
    insp = sa_inspect(conn)
    existing_tables = insp.get_table_names()

    # --- Unique constraints on business keys (composite with tenant_id) ---
    # De-duplicate existing data before adding constraints, and use unique indexes
    # (which are equivalent to unique constraints but can be created IF NOT EXISTS-style).
    pairs = [
        ("opportunity_projects", "uq_project_tenant_code", ["tenant_id", "project_code"], "project_code"),
        ("quotes", "uq_quote_tenant_no", ["tenant_id", "quote_no"], "quote_no"),
        ("contracts", "uq_contract_tenant_no", ["tenant_id", "contract_no"], "contract_no"),
        ("invoices", "uq_invoice_tenant_no", ["tenant_id", "invoice_no"], "invoice_no"),
        ("payment_plans", "uq_plan_tenant_no", ["tenant_id", "plan_no"], "plan_no"),
    ]
    from sqlalchemy import text
    for table, name, cols, code_col in pairs:
        if table not in existing_tables:
            continue
        if _constraint_exists(conn, table, name):
            continue
        # De-duplicate: keep only the row with the latest created_at per (tenant_id, code_col)
        dedup_sql = text(f"""
            DELETE FROM {table} WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY tenant_id, {code_col} ORDER BY created_at DESC
                    ) AS rn FROM {table}
                ) sub WHERE rn > 1
            )
        """)
        conn.execute(dedup_sql)
        # Now safe to add unique constraint
        op.create_unique_constraint(name, table, cols)

    # --- Soft-delete composite indexes ---
    soft_delete_indexes = [
        ("customers", "ix_customer_tenant_deleted", ["tenant_id", "is_deleted"]),
        ("leads", "ix_lead_tenant_deleted", ["tenant_id", "is_deleted"]),
    ]
    for table, name, cols in soft_delete_indexes:
        if table not in existing_tables:
            continue
        if not _index_exists(conn, table, name):
            op.create_index(name, table, cols)


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
