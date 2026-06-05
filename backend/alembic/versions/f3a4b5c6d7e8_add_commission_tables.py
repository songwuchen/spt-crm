"""add commission tables

业务提成/奖金核算：提成单(commission_records)、提成政策(commission_rules)、
支付明细(commission_payouts)。回款驱动的奖金计算。

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    if "commission_rules" not in existing:
        op.create_table(
            "commission_rules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("scope_type", sa.String(16), default="all"),
            sa.Column("department_id", sa.String(36), index=True),
            sa.Column("department_name", sa.String(100)),
            sa.Column("rate", sa.Numeric(8, 4), default=0),
            sa.Column("min_amount", sa.Numeric(18, 2)),
            sa.Column("enabled", sa.Boolean, default=True),
            sa.Column("sort_order", sa.Integer, default=0),
            sa.Column("remark", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    if "commission_records" not in existing:
        op.create_table(
            "commission_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("record_no", sa.String(64), nullable=False),
            sa.Column("project_id", sa.String(36), index=True),
            sa.Column("contract_id", sa.String(36), index=True),
            sa.Column("customer_id", sa.String(36), index=True),
            sa.Column("customer_name", sa.String(300)),
            sa.Column("owner_id", sa.String(36), index=True),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("department_id", sa.String(36)),
            sa.Column("department_name", sa.String(100)),
            sa.Column("signed_date", sa.Date),
            sa.Column("contract_amount", sa.Numeric(18, 2), default=0),
            sa.Column("received_amount", sa.Numeric(18, 2), default=0),
            sa.Column("deduction_freight", sa.Numeric(18, 2), default=0),
            sa.Column("deduction_service", sa.Numeric(18, 2), default=0),
            sa.Column("deduction_entertain", sa.Numeric(18, 2), default=0),
            sa.Column("deduction_rebate", sa.Numeric(18, 2), default=0),
            sa.Column("commission_rate", sa.Numeric(8, 4), default=0),
            sa.Column("settle_rate", sa.Numeric(8, 4), default=0),
            sa.Column("accrued_amount", sa.Numeric(18, 2), default=0),
            sa.Column("paid_amount", sa.Numeric(18, 2), default=0),
            sa.Column("current_amount", sa.Numeric(18, 2), default=0),
            sa.Column("status", sa.String(16), default="draft"),
            sa.Column("remark", sa.Text),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_commission_tenant_owner", "commission_records", ["tenant_id", "owner_id"])

    if "commission_payouts" not in existing:
        op.create_table(
            "commission_payouts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("commission_id", sa.String(36), nullable=False, index=True),
            sa.Column("paid_at", sa.Date),
            sa.Column("amount", sa.Numeric(18, 2), default=0),
            sa.Column("method", sa.String(64)),
            sa.Column("remark", sa.Text),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()
    for t in ("commission_payouts", "commission_records", "commission_rules"):
        if t in existing:
            op.drop_table(t)
