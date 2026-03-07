"""add login_sessions table

Revision ID: i1a2b3c4d5e6
Revises: h0c1d2e3f4a5
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "i1a2b3c4d5e6"
down_revision = "h0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 2FA and password policy fields to users
    op.add_column("users", sa.Column("totp_secret", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean, server_default="false"))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "login_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_jti", sa.String(64), unique=True, nullable=False),
        sa.Column("ip", sa.String(50)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("device_type", sa.String(30)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        sa.Column("is_deleted", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    op.create_index("ix_login_sessions_token_jti", "login_sessions", ["token_jti"])

    # Saved views table
    op.create_table(
        "saved_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("page", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("is_default", sa.Boolean, default=False),
        sa.Column("is_deleted", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_saved_views_user_page", "saved_views", ["user_id", "page"])


def downgrade() -> None:
    op.drop_table("login_sessions")
    op.drop_table("saved_views")
    op.drop_column("users", "totp_secret")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "password_changed_at")
