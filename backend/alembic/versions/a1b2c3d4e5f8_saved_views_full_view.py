"""extend saved_views for full views (columns + sort + visibility)

Adds to saved_views:
- columns_json: 列配置 {hidden:[], order:[]}
- sort_by / sort_order: 排序
- visibility: private / tenant（租户共享）

Revision ID: a1b2c3d4e5f8
Revises: f0a1b2c3d4e5
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "a1b2c3d4e5f8"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "saved_views" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("saved_views")}

    if "columns_json" not in cols:
        op.add_column("saved_views", sa.Column("columns_json", sa.Text(), nullable=True))
    if "sort_by" not in cols:
        op.add_column("saved_views", sa.Column("sort_by", sa.String(64), nullable=True))
    if "sort_order" not in cols:
        op.add_column("saved_views", sa.Column("sort_order", sa.String(8), nullable=True))
    if "visibility" not in cols:
        op.add_column("saved_views", sa.Column("visibility", sa.String(16), nullable=True, server_default="private"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "saved_views" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("saved_views")}
    for col in ("visibility", "sort_order", "sort_by", "columns_json"):
        if col in cols:
            op.drop_column("saved_views", col)
