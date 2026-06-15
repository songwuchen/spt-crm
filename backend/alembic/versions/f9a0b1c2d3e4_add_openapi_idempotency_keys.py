"""add openapi_idempotency_keys table (写接口幂等键)

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "openapi_idempotency_keys" in sa_inspect(bind).get_table_names():
        return
    op.create_table(
        "openapi_idempotency_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("app_key", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(128), nullable=False),
        sa.Column("response_json", sa.JSON),
        sa.Column("status_code", sa.Integer),
        sa.Column("status", sa.String(16), server_default="processing"),
        sa.Column("expires_at", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(
        "ux_openapi_idem", "openapi_idempotency_keys",
        ["tenant_id", "app_key", "idempotency_key"], unique=True,
    )


def downgrade() -> None:
    if "openapi_idempotency_keys" in sa_inspect(op.get_bind()).get_table_names():
        op.drop_table("openapi_idempotency_keys")
