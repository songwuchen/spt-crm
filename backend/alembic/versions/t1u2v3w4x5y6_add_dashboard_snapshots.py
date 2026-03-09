"""add dashboard snapshots table

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dashboard_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("share_token", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_by_name", sa.String(100)),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("card_visibility_json", sa.Text()),
        sa.Column("card_order_json", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table("dashboard_snapshots")
