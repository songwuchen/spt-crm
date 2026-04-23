"""add classification fields to leads (issue #17)

Adds customer_type, industry enum migration, category (自报/分发),
country_type/country_name, province/city/district, department_id.

Revision ID: b9c0d1e2f3g4
Revises: a8b9c0d1e2f3
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "b9c0d1e2f3g4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("customer_type", sa.String(50), nullable=True))
    op.add_column("leads", sa.Column("category", sa.String(20), nullable=True))
    op.add_column("leads", sa.Column("country_type", sa.String(20), nullable=True))
    op.add_column("leads", sa.Column("country_name", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("province", sa.String(50), nullable=True))
    op.add_column("leads", sa.Column("city", sa.String(50), nullable=True))
    op.add_column("leads", sa.Column("district", sa.String(50), nullable=True))
    op.add_column("leads", sa.Column("department_id", sa.String(36), nullable=True))

    # Indexes chosen to match expected filter patterns on the list page
    op.create_index("ix_leads_customer_type", "leads", ["tenant_id", "customer_type"])
    op.create_index("ix_leads_category", "leads", ["tenant_id", "category"])
    op.create_index("ix_leads_country_type", "leads", ["tenant_id", "country_type"])
    op.create_index("ix_leads_province", "leads", ["tenant_id", "province"])
    op.create_index("ix_leads_department_id", "leads", ["tenant_id", "department_id"])


def downgrade() -> None:
    op.drop_index("ix_leads_department_id", table_name="leads")
    op.drop_index("ix_leads_province", table_name="leads")
    op.drop_index("ix_leads_country_type", table_name="leads")
    op.drop_index("ix_leads_category", table_name="leads")
    op.drop_index("ix_leads_customer_type", table_name="leads")

    op.drop_column("leads", "department_id")
    op.drop_column("leads", "district")
    op.drop_column("leads", "city")
    op.drop_column("leads", "province")
    op.drop_column("leads", "country_name")
    op.drop_column("leads", "country_type")
    op.drop_column("leads", "category")
    op.drop_column("leads", "customer_type")
