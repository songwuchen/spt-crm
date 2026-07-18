"""add dept_role_rules (department -> role auto-assignment)

Revision ID: da1b2c3d4e5f
Revises: cf10a1b2c3d4
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = "da1b2c3d4e5f"
down_revision = "cf10a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dept_role_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("department_id", sa.String(36), nullable=False),
        sa.Column("role_id", sa.String(36), nullable=False),
        sa.Column("include_children", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        # FK constraints mirror the model (ForeignKey) and the codebase convention
        # (user_roles / user_departments in the init migration both carry them).
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
    )
    op.create_index(
        "uq_dept_role_rule",
        "dept_role_rules",
        ["tenant_id", "department_id", "role_id"],
        unique=True,
    )
    # role 维度清理/查询走索引
    op.create_index(
        "ix_dept_role_rule_role",
        "dept_role_rules",
        ["tenant_id", "role_id"],
    )


def downgrade():
    op.drop_index("ix_dept_role_rule_role", table_name="dept_role_rules")
    op.drop_index("uq_dept_role_rule", table_name="dept_role_rules")
    op.drop_table("dept_role_rules")
