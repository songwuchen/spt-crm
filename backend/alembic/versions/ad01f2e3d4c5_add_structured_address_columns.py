"""add structured address columns to customers and leads

给客户/线索补齐结构化省市区级联地址：
- customers 新增 province / city / district（名称）+ region_code（行政区划编码 GB/T 2260，最深选中层级）
- leads 新增 region_code（province/city/district 已存在）
- region_code 建索引，支持按编码前缀做层级过滤（选到市即命中全市各区）

Revision ID: ad01f2e3d4c5
Revises: ai01c2d3e4f5
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = "ad01f2e3d4c5"
down_revision = "ai01c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customers", sa.Column("province", sa.String(length=50), nullable=True))
    op.add_column("customers", sa.Column("city", sa.String(length=50), nullable=True))
    op.add_column("customers", sa.Column("district", sa.String(length=50), nullable=True))
    op.add_column("customers", sa.Column("region_code", sa.String(length=12), nullable=True))
    op.create_index(op.f("ix_customers_region_code"), "customers", ["region_code"], unique=False)

    op.add_column("leads", sa.Column("region_code", sa.String(length=12), nullable=True))
    op.create_index(op.f("ix_leads_region_code"), "leads", ["region_code"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_leads_region_code"), table_name="leads")
    op.drop_column("leads", "region_code")

    op.drop_index(op.f("ix_customers_region_code"), table_name="customers")
    op.drop_column("customers", "region_code")
    op.drop_column("customers", "district")
    op.drop_column("customers", "city")
    op.drop_column("customers", "province")
