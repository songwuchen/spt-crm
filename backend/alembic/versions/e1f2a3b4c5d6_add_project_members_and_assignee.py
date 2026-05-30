"""add project_members table and assignee fields to sub-modules

商机多部门/多人协作：
- project_members: 商机团队成员（角色/部门/读写权限）
- 子模块负责人字段 assignee_id/assignee_name/department_id/department_name
  加到 solutions / quotes / contracts / change_requests / delivery_milestones / payment_plans

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3g4h5i6
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "e1f2a3b4c5d6"
down_revision = "d1e2f3g4h5i6"
branch_labels = None
depends_on = None

# Tables that gain the assignee (子模块负责人) columns
ASSIGNEE_TABLES = [
    "solutions",
    "quotes",
    "contracts",
    "change_requests",
    "delivery_milestones",
    "payment_plans",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()

    if "project_members" not in existing_tables:
        op.create_table(
            "project_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("project_id", sa.String(36), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), nullable=False, index=True),
            sa.Column("user_name", sa.String(100)),
            sa.Column("member_role", sa.String(32)),
            sa.Column("department_id", sa.String(36)),
            sa.Column("department_name", sa.String(100)),
            sa.Column("permission", sa.String(16), default="view"),
            sa.Column("added_by_id", sa.String(36)),
            sa.Column("added_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index(
            "uq_project_members_tpu", "project_members",
            ["tenant_id", "project_id", "user_id"], unique=True,
        )

    for table in ASSIGNEE_TABLES:
        if table not in existing_tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "assignee_id" not in cols:
            op.add_column(table, sa.Column("assignee_id", sa.String(36), nullable=True))
            op.create_index(f"ix_{table}_assignee_id", table, ["assignee_id"])
        if "assignee_name" not in cols:
            op.add_column(table, sa.Column("assignee_name", sa.String(100), nullable=True))
        if "department_id" not in cols:
            op.add_column(table, sa.Column("department_id", sa.String(36), nullable=True))
        if "department_name" not in cols:
            op.add_column(table, sa.Column("department_name", sa.String(100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()

    for table in ASSIGNEE_TABLES:
        if table not in existing_tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        indexes = {i["name"] for i in inspector.get_indexes(table)}
        if f"ix_{table}_assignee_id" in indexes:
            op.drop_index(f"ix_{table}_assignee_id", table_name=table)
        for col in ("department_name", "department_id", "assignee_name", "assignee_id"):
            if col in cols:
                op.drop_column(table, col)

    if "project_members" in existing_tables:
        op.drop_table("project_members")
