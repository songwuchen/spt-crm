"""add department_id to sales_targets

Revision ID: a8b9c0d1e2f3
Revises: w4x5y6z7a8b9
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "a8b9c0d1e2f3"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sales_targets", sa.Column("department_id", sa.String(36), nullable=True))
    op.add_column("sales_targets", sa.Column("department_name", sa.String(200), nullable=True))
    # Make user_id nullable so department-level targets can omit it
    op.alter_column("sales_targets", "user_id", existing_type=sa.String(36), nullable=True)
    # Unique index for department targets
    op.create_index(
        "ix_sales_targets_tenant_dept_period",
        "sales_targets",
        ["tenant_id", "department_id", "year", "month"],
        unique=True,
        postgresql_where=sa.text("department_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("ix_sales_targets_tenant_dept_period", "sales_targets")
    op.alter_column("sales_targets", "user_id", existing_type=sa.String(36), nullable=False)
    op.drop_column("sales_targets", "department_name")
    op.drop_column("sales_targets", "department_id")
