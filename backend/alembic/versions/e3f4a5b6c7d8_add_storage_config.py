"""add tenant file storage config + attachment storage_backend

Adds:
- tenant_storage_configs: per-tenant选择本地/MinIO/阿里云OSS及凭证
- attachments.storage_backend: 记录每个文件实际存放的后端（切换后端后历史文件仍可访问）

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "e3f4a5b6c7d8"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "tenant_storage_configs" not in insp.get_table_names():
        op.create_table(
            "tenant_storage_configs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("storage_type", sa.String(16), nullable=True, server_default="local"),
            sa.Column("config_json", sa.JSON(), nullable=True),
        )

    att_cols = {c["name"] for c in insp.get_columns("attachments")}
    if "storage_backend" not in att_cols:
        op.add_column(
            "attachments",
            sa.Column("storage_backend", sa.String(16), nullable=True, server_default="local"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    att_cols = {c["name"] for c in insp.get_columns("attachments")}
    if "storage_backend" in att_cols:
        op.drop_column("attachments", "storage_backend")

    if "tenant_storage_configs" in insp.get_table_names():
        op.drop_table("tenant_storage_configs")
