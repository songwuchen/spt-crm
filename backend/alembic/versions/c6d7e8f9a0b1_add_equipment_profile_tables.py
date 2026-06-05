"""add customer equipment + process survey tables

客户工艺与设备档案（精细化营销）：设备台账 customer_equipments、工艺调研 customer_process_surveys。

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = sa_inspect(bind).get_table_names()

    if "customer_equipments" not in existing:
        op.create_table(
            "customer_equipments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("customer_id", sa.String(36), nullable=False, index=True),
            sa.Column("customer_name", sa.String(300)),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(64)),
            sa.Column("spec", sa.String(200)),
            sa.Column("supplier", sa.String(200)),
            sa.Column("is_competitor", sa.Boolean, default=False, index=True),
            sa.Column("usage_years", sa.Numeric(6, 1)),
            sa.Column("quantity", sa.Integer),
            sa.Column("condition", sa.Text),
            sa.Column("replace_plan_date", sa.Date, index=True),
            sa.Column("spare_usage", sa.Text),
            sa.Column("remark", sa.Text),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    if "customer_process_surveys" not in existing:
        op.create_table(
            "customer_process_surveys",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("customer_id", sa.String(36), nullable=False, index=True),
            sa.Column("customer_name", sa.String(300)),
            sa.Column("industry", sa.String(64)),
            sa.Column("main_products", sa.String(300)),
            sa.Column("annual_output", sa.String(100)),
            sa.Column("branch_info", sa.Text),
            sa.Column("process_desc", sa.Text),
            sa.Column("pain_points", sa.Text),
            sa.Column("survey_date", sa.Date),
            sa.Column("owner_id", sa.String(36)),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("remark", sa.Text),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )


def downgrade() -> None:
    existing = sa_inspect(op.get_bind()).get_table_names()
    for t in ("customer_process_surveys", "customer_equipments"):
        if t in existing:
            op.drop_table(t)
