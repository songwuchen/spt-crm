"""add data dictionaries table

Revision ID: j2b3c4d5e6f7
Revises: i1a2b3c4d5e6
Create Date: 2026-03-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "j2b3c4d5e6f7"
down_revision = "i1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_dictionaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("dict_type", sa.String(64), nullable=False, index=True),
        sa.Column("dict_code", sa.String(64), nullable=False),
        sa.Column("dict_label", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("color", sa.String(32)),
        sa.Column("extra_json", sa.JSON),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("is_deleted", sa.Boolean, default=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_data_dict_tenant_type", "data_dictionaries", ["tenant_id", "dict_type"])


def downgrade():
    op.drop_index("ix_data_dict_tenant_type", "data_dictionaries")
    op.drop_table("data_dictionaries")
