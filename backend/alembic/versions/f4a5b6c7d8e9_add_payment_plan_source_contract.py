"""add payment_plans.source_contract_id

记录回款计划由哪个合同生成（null = 手工创建），用于按合同范围覆盖重生成。

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("payment_plans")}
    if "source_contract_id" not in cols:
        op.add_column("payment_plans", sa.Column("source_contract_id", sa.String(36), nullable=True))
    idx = {i["name"] for i in insp.get_indexes("payment_plans")}
    if "ix_payment_plans_source_contract_id" not in idx:
        op.create_index("ix_payment_plans_source_contract_id", "payment_plans", ["source_contract_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    idx = {i["name"] for i in insp.get_indexes("payment_plans")}
    if "ix_payment_plans_source_contract_id" in idx:
        op.drop_index("ix_payment_plans_source_contract_id", table_name="payment_plans")
    cols = {c["name"] for c in insp.get_columns("payment_plans")}
    if "source_contract_id" in cols:
        op.drop_column("payment_plans", "source_contract_id")
