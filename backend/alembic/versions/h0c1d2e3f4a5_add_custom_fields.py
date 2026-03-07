"""add custom fields

Revision ID: h0c1d2e3f4a5
Revises: g9b0c1d2e3f4
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "h0c1d2e3f4a5"
down_revision = "g9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade():
    # Custom field definitions table
    op.create_table(
        "custom_field_defs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("entity_type", sa.String(32), nullable=False, index=True),
        sa.Column("field_key", sa.String(64), nullable=False),
        sa.Column("field_label", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(32), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("required", sa.Boolean(), default=False),
        sa.Column("sort_order", sa.Integer(), default=0),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Add custom_fields_json to customers and opportunity_projects
    op.add_column("customers", sa.Column("custom_fields_json", sa.JSON(), nullable=True))
    op.add_column("opportunity_projects", sa.Column("custom_fields_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("opportunity_projects", "custom_fields_json")
    op.drop_column("customers", "custom_fields_json")
    op.drop_table("custom_field_defs")
