"""merge alembic heads + pickable_scopes table

Revision ID: ps01a2b3c4d5
Revises: so01a2b3c4d5, c3d4e5f6a7b8
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision = "ps01a2b3c4d5"
down_revision = ("so01a2b3c4d5", "c3d4e5f6a7b8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "pickable_scopes" in inspector.get_table_names():
        return
    op.create_table(
        "pickable_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="person"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_pickable_scopes_tenant_code"),
    )
    op.create_index("ix_pickable_scopes_tenant_kind", "pickable_scopes", ["tenant_id", "kind"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "pickable_scopes" not in inspector.get_table_names():
        return
    op.drop_index("ix_pickable_scopes_tenant_kind", table_name="pickable_scopes")
    op.drop_table("pickable_scopes")
