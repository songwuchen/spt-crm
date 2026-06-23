"""add order_lines table (订单明细：产品/规格/单位/数量/单价/金额 + 已发货数量)

支持订单按明细汇总合计金额，以及部分/全部发货（shipped_quantity）。

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "order_lines" in insp.get_table_names():
        return
    op.create_table(
        "order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), nullable=True),
        sa.Column("product_name", sa.String(300), nullable=False),
        sa.Column("spec", sa.String(200), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("shipped_quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "order_lines" in insp.get_table_names():
        op.drop_table("order_lines")
