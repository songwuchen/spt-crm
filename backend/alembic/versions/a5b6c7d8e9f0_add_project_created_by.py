"""add opportunity_projects.created_by_id / created_by_name

录入人(创建人)与负责人分家：负责人(owner)可由主管经转移接口改派，
录入人(created_by)永久保留以供溯源。历史数据中负责人即为创建人，故回填 created_by = owner。

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("opportunity_projects")}
    if "created_by_id" not in cols:
        op.add_column("opportunity_projects", sa.Column("created_by_id", sa.String(36), nullable=True))
    if "created_by_name" not in cols:
        op.add_column("opportunity_projects", sa.Column("created_by_name", sa.String(100), nullable=True))
    # 回填：历史记录的负责人即为录入人
    op.execute(
        "UPDATE opportunity_projects "
        "SET created_by_id = owner_id, created_by_name = owner_name "
        "WHERE created_by_id IS NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("opportunity_projects")}
    if "created_by_name" in cols:
        op.drop_column("opportunity_projects", "created_by_name")
    if "created_by_id" in cols:
        op.drop_column("opportunity_projects", "created_by_id")
