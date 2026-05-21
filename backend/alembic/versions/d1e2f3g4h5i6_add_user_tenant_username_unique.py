"""add unique constraint on users(tenant_id, username)

Usernames must be unique within a tenant. Without this, two tenants could hold the
same username and login resolution would be ambiguous (see auth.service.authenticate).

This migration is conservative: it will NOT delete duplicate user accounts automatically
(unlike the business-code de-duplication in w4x5y6z7a8b9). If duplicates exist it raises a
clear error so an operator can reconcile the accounts manually before re-running.

Revision ID: d1e2f3g4h5i6
Revises: c0d1e2f3g4h5
Create Date: 2026-05-21
"""
from alembic import op
from sqlalchemy import inspect as sa_inspect, text

revision = "d1e2f3g4h5i6"
down_revision = "c0d1e2f3g4h5"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_user_tenant_username"


def _constraint_exists(conn, table_name, constraint_name) -> bool:
    insp = sa_inspect(conn)
    return any(uc["name"] == constraint_name for uc in insp.get_unique_constraints(table_name))


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa_inspect(conn)
    if "users" not in insp.get_table_names():
        return
    if _constraint_exists(conn, "users", CONSTRAINT_NAME):
        return

    # Refuse to silently delete accounts — surface duplicates for manual reconciliation.
    dupes = conn.execute(text(
        """
        SELECT tenant_id, username, COUNT(*) AS n
        FROM users
        GROUP BY tenant_id, username
        HAVING COUNT(*) > 1
        """
    )).fetchall()
    if dupes:
        detail = ", ".join(f"(tenant={r[0]}, username={r[1]}, count={r[2]})" for r in dupes)
        raise RuntimeError(
            "Cannot add unique constraint uq_user_tenant_username: duplicate "
            f"(tenant_id, username) rows exist and must be reconciled manually: {detail}"
        )

    op.create_unique_constraint(CONSTRAINT_NAME, "users", ["tenant_id", "username"])


def downgrade() -> None:
    try:
        op.drop_constraint(CONSTRAINT_NAME, "users", type_="unique")
    except Exception:
        pass
