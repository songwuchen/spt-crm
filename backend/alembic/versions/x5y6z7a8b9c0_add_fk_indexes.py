"""Add indexes on foreign key columns for query performance.

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-03-11
"""
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "x5y6z7a8b9c0"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None

# (table_name, column_name) pairs for FK index creation
FK_INDEXES = [
    # Auth — hot path on every request
    ("user_roles", "user_id"),
    ("user_roles", "role_id"),
    ("role_permissions", "role_id"),
    ("role_permissions", "permission_id"),
    ("login_sessions", "user_id"),
    # Organization
    ("departments", "parent_id"),
    ("departments", "leader_id"),
    ("user_departments", "user_id"),
    ("user_departments", "department_id"),
    # Customer
    ("customers", "owner_id"),
    ("contacts", "reports_to_id"),
    ("acl_shares", "shared_to_id"),
    ("acl_shares", "shared_by_id"),
    # Lead
    ("leads", "owner_id"),
    ("leads", "converted_customer_id"),
    # Project
    ("opportunity_projects", "owner_id"),
    ("project_stage_history", "changed_by_id"),
    # Quote
    ("quotes", "created_by_id"),
    ("cost_snapshots", "created_by_id"),
    ("quote_send_logs", "sent_by_id"),
    # Contract
    ("contracts", "created_by_id"),
    ("contract_versions", "doc_attachment_id"),
    # Payment
    ("invoices", "created_by_id"),
    ("payment_records", "matched_plan_id"),
    ("payment_records", "created_by_id"),
    # Service
    ("service_tickets", "assigned_to_id"),
    ("service_tickets", "created_by_id"),
    ("renewal_opportunities", "owner_id"),
    # Activity
    ("activities", "created_by_id"),
    # Change
    ("change_requests", "created_by_id"),
    # Approval
    ("approval_flows", "submitted_by_id"),
    ("approval_flows", "parent_flow_id"),
    # Attachment
    ("attachments", "uploader_id"),
    # Audit
    ("audit_logs", "user_id"),
    # Notification
    ("notifications", "biz_id"),
    # AI
    ("ai_tasks", "created_by_id"),
    ("ai_tasks", "prompt_template_id"),
    # Solution
    ("solutions", "created_by_id"),
    ("solution_versions", "doc_attachment_id"),
    # Task
    ("user_tasks", "created_by_id"),
    ("user_tasks", "biz_id"),
    # Product
    ("product_categories", "parent_id"),
    # Admin
    ("doc_templates", "created_by_id"),
]


def _has_index(conn, table_name, column_name):
    """Check if an index already exists for the given column."""
    try:
        insp = sa_inspect(conn)
        if table_name not in insp.get_table_names():
            return True  # table doesn't exist, skip
        indexes = insp.get_indexes(table_name)
        for idx in indexes:
            cols = idx.get("column_names", [])
            if column_name in cols and len(cols) == 1:
                return True
        # Also check unique constraints (they create implicit indexes)
        uqs = insp.get_unique_constraints(table_name)
        for uq in uqs:
            cols = uq.get("column_names", [])
            if column_name in cols and len(cols) == 1:
                return True
    except Exception:
        pass
    return False


def upgrade():
    conn = op.get_bind()
    for table, col in FK_INDEXES:
        if not _has_index(conn, table, col):
            idx_name = f"ix_{table}_{col}"
            op.create_index(idx_name, table, [col])


def downgrade():
    for table, col in reversed(FK_INDEXES):
        idx_name = f"ix_{table}_{col}"
        try:
            op.drop_index(idx_name, table_name=table)
        except Exception:
            pass
