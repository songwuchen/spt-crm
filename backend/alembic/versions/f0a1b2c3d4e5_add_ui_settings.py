"""add ui settings columns to tenant_profiles (界面设置)

Adds to tenant_profiles:
- system_name: 系统显示名（品牌名），空=默认
- menu_aliases_json: {菜单key: 别名}
- hidden_menus_json: 隐藏的菜单key列表

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("tenant_profiles")}

    if "system_name" not in cols:
        op.add_column("tenant_profiles", sa.Column("system_name", sa.String(64), nullable=True))
    if "menu_aliases_json" not in cols:
        op.add_column("tenant_profiles", sa.Column("menu_aliases_json", sa.JSON(), nullable=True))
    if "hidden_menus_json" not in cols:
        op.add_column("tenant_profiles", sa.Column("hidden_menus_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("tenant_profiles")}

    for col in ("hidden_menus_json", "menu_aliases_json", "system_name"):
        if col in cols:
            op.drop_column("tenant_profiles", col)
