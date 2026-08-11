"""align customers with JDY 数据中心「客户信息」fields + contact.department

Revision ID: cu01a2b3c4d5
Revises: tar01a2b3c4d5
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "cu01a2b3c4d5"
down_revision = "tar01a2b3c4d5"
branch_labels = None
depends_on = None

_CUSTOMER_COLUMNS = [
    ("is_smart_filing", sa.Column("is_smart_filing", sa.Boolean(), nullable=True)),
    ("is_foreign_trade", sa.Column("is_foreign_trade", sa.Boolean(), nullable=True)),
    ("registered_capital", sa.Column("registered_capital", sa.Numeric(18, 2), nullable=True)),
    ("paid_in_capital", sa.Column("paid_in_capital", sa.Numeric(18, 2), nullable=True)),
    ("founded_year", sa.Column("founded_year", sa.Integer(), nullable=True)),
    ("parent_company_note", sa.Column("parent_company_note", sa.Text(), nullable=True)),
    ("customer_nature", sa.Column("customer_nature", sa.String(50), nullable=True)),
    ("customer_relation", sa.Column("customer_relation", sa.String(50), nullable=True)),
    ("primary_contact_title", sa.Column("primary_contact_title", sa.String(100), nullable=True)),
    ("wage_insurance_status", sa.Column("wage_insurance_status", sa.String(50), nullable=True)),
    ("is_company_customer", sa.Column("is_company_customer", sa.Boolean(), nullable=True)),
    ("taxpayer_id", sa.Column("taxpayer_id", sa.String(64), nullable=True)),
    ("invoice_address_phone", sa.Column("invoice_address_phone", sa.String(300), nullable=True)),
    ("bank_account", sa.Column("bank_account", sa.String(200), nullable=True)),
    ("foreign_customer_code", sa.Column("foreign_customer_code", sa.String(100), nullable=True)),
    ("foreign_customer_type", sa.Column("foreign_customer_type", sa.String(50), nullable=True)),
    ("focus_product", sa.Column("focus_product", sa.String(100), nullable=True)),
    ("customer_email", sa.Column("customer_email", sa.String(200), nullable=True)),
    ("main_products_json", sa.Column("main_products_json", sa.JSON(), nullable=True)),
    ("legal_person", sa.Column("legal_person", sa.String(100), nullable=True)),
    ("smart_industry_category", sa.Column("smart_industry_category", sa.String(200), nullable=True)),
    ("annual_run_days", sa.Column("annual_run_days", sa.String(50), nullable=True)),
    ("floor_area", sa.Column("floor_area", sa.String(100), nullable=True)),
    ("financial_status", sa.Column("financial_status", sa.Text(), nullable=True)),
    ("business_status", sa.Column("business_status", sa.Text(), nullable=True)),
    ("annual_power_usage", sa.Column("annual_power_usage", sa.String(100), nullable=True)),
    ("daily_operate_hours", sa.Column("daily_operate_hours", sa.String(50), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    existing = {c["name"] for c in insp.get_columns("customers")}
    for name, col in _CUSTOMER_COLUMNS:
        if name not in existing:
            op.add_column("customers", col)

    contact_cols = {c["name"] for c in insp.get_columns("contacts")}
    if "department" not in contact_cols:
        op.add_column("contacts", sa.Column("department", sa.String(100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    contact_cols = {c["name"] for c in insp.get_columns("contacts")}
    if "department" in contact_cols:
        op.drop_column("contacts", "department")
    existing = {c["name"] for c in insp.get_columns("customers")}
    for name, _ in reversed(_CUSTOMER_COLUMNS):
        if name in existing:
            op.drop_column("customers", name)
