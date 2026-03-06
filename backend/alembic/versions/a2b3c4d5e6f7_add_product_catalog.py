"""add product catalog

Revision ID: a2b3c4d5e6f7
Revises: b3c4d5e6f7a8
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("product_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=True, index=True),
        sa.Column("item_type", sa.String(16), nullable=True),
        sa.Column("spec", sa.String(500), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("cost_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("leadtime_days", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("extra_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_index("ix_products_tenant_code", "products", ["tenant_id", "product_code"], unique=True)


def downgrade():
    op.drop_index("ix_products_tenant_code", "products")
    op.drop_table("products")
    op.drop_table("product_categories")
