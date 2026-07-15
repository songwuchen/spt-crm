"""add custom_fields_json to more entities (Phase 2 unify)

为 leads/orders/service_tickets/contacts 增加 custom_fields_json(JSON, 可空),
统一自定义字段到表单引擎(值存业务表, schema 存系统表单模板)。纯新增列,安全前滚/回滚。

Revision ID: lc004d4e5f6a
Revises: lc003c3d4e5f
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "lc004d4e5f6a"
down_revision = "lc003c3d4e5f"
branch_labels = None
depends_on = None

_TABLES = ["leads", "orders", "service_tickets", "contacts"]


def upgrade():
    for t in _TABLES:
        op.add_column(t, sa.Column("custom_fields_json", sa.JSON(), nullable=True))


def downgrade():
    for t in _TABLES:
        op.drop_column(t, "custom_fields_json")
