"""user_managed_departments: 用户负责的业务部门（线索内勤可见范围）

Revision ID: um01a2b3c4d5
Revises: cui01a2b3c4d5
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect, text

revision = "um01a2b3c4d5"
down_revision = "cui01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "user_managed_departments" not in insp.get_table_names():
        op.create_table(
            "user_managed_departments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id"), nullable=False),
        )
        op.create_index(
            "uq_user_managed_dept",
            "user_managed_departments",
            ["tenant_id", "user_id", "department_id"],
            unique=True,
        )
        op.create_index(
            "ix_user_managed_dept_user",
            "user_managed_departments",
            ["tenant_id", "user_id"],
        )

    # 信息情报部内勤：由「全部」收窄为「本人 + 负责业务部门」
    bind.execute(text(
        "UPDATE roles SET data_scope = 'self' "
        "WHERE code = 'lead_intel' AND (data_scope IS NULL OR data_scope = 'all')"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "user_managed_departments" in insp.get_table_names():
        op.drop_index("ix_user_managed_dept_user", table_name="user_managed_departments")
        op.drop_index("uq_user_managed_dept", table_name="user_managed_departments")
        op.drop_table("user_managed_departments")
    bind.execute(text(
        "UPDATE roles SET data_scope = 'all' WHERE code = 'lead_intel' AND data_scope = 'self'"
    ))
