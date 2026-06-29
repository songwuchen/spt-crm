"""add commission_records.commission_mode / commission_amount

部分合同的提成不按比例计算，而是约定固定金额（issue #70）。新增提成方式
(commission_mode: rate/amount) 与固定提成金额(commission_amount)。
金额模式下：应计奖金 = 提成金额 × 回款结算比例（与「回款驱动」一致）。

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("commission_records")}
    if "commission_mode" not in cols:
        op.add_column("commission_records", sa.Column(
            "commission_mode", sa.String(8), nullable=False, server_default="rate"))
    if "commission_amount" not in cols:
        op.add_column("commission_records", sa.Column(
            "commission_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = {c["name"] for c in insp.get_columns("commission_records")}
    if "commission_amount" in cols:
        op.drop_column("commission_records", "commission_amount")
    if "commission_mode" in cols:
        op.drop_column("commission_records", "commission_mode")
