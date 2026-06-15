"""add openapi platform tables (开放平台：应用 + 调用日志)

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa_inspect(bind).get_table_names())

    if "openapi_apps" not in existing:
        op.create_table(
            "openapi_apps",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("app_key", sa.String(64), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("app_type", sa.String(64), server_default="external_system"),
            sa.Column("auth_mode", sa.String(16), server_default="apikey"),
            sa.Column("status", sa.String(16), server_default="enabled"),
            sa.Column("scopes_json", sa.JSON),
            sa.Column("secret_hash", sa.String(128), nullable=False),
            sa.Column("secret_enc", sa.Text),
            sa.Column("secret_prefix", sa.String(32)),
            sa.Column("rate_limit_per_minute", sa.Integer, server_default="600"),
            sa.Column("ip_whitelist_json", sa.JSON),
            sa.Column("is_deleted", sa.Boolean, server_default=sa.false(), index=True),
            sa.Column("remark", sa.String(500)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_openapi_apps_app_key", "openapi_apps", ["app_key"], unique=True)
        op.create_index("ix_openapi_apps_secret_hash", "openapi_apps", ["secret_hash"], unique=True)

    if "openapi_call_logs" not in existing:
        op.create_table(
            "openapi_call_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("trace_id", sa.String(64), index=True),
            sa.Column("app_key", sa.String(64), nullable=False, index=True),
            sa.Column("method", sa.String(16)),
            sa.Column("path", sa.String(500)),
            sa.Column("query_string", sa.String(1000)),
            sa.Column("status_code", sa.Integer),
            sa.Column("error_code", sa.String(128)),
            sa.Column("duration_ms", sa.Integer),
            sa.Column("client_ip", sa.String(64)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_openapi_call_logs_app_time", "openapi_call_logs", ["app_key", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa_inspect(bind).get_table_names())
    if "openapi_call_logs" in existing:
        op.drop_table("openapi_call_logs")
    if "openapi_apps" in existing:
        op.drop_table("openapi_apps")
