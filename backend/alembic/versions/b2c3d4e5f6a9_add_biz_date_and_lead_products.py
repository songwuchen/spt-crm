"""add biz_date to leads/opportunity_projects + lead_products table (issue #84)

线索/商机新增可编辑「业务日期」biz_date（区别于系统 created_at 与预计成交日）；
新增线索产品信息子表 lead_products（产品名称/规格/数量/备注）。

Revision ID: b2c3d4e5f6a9
Revises: a1b2c3d4e5f8
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "b2c3d4e5f6a9"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "leads" in insp.get_table_names() and not _has_column(insp, "leads", "biz_date"):
        op.add_column("leads", sa.Column("biz_date", sa.Date(), nullable=True))

    if "opportunity_projects" in insp.get_table_names() and not _has_column(insp, "opportunity_projects", "biz_date"):
        op.add_column("opportunity_projects", sa.Column("biz_date", sa.Date(), nullable=True))

    if "lead_products" not in insp.get_table_names():
        op.create_table(
            "lead_products",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("lead_id", sa.String(36), nullable=False, index=True),
            sa.Column("product_name", sa.String(300), nullable=True),
            sa.Column("product_spec", sa.String(300), nullable=True),
            sa.Column("quantity", sa.Numeric(18, 3), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "lead_products" in insp.get_table_names():
        op.drop_table("lead_products")
    if _has_column(insp, "opportunity_projects", "biz_date"):
        op.drop_column("opportunity_projects", "biz_date")
    if _has_column(insp, "leads", "biz_date"):
        op.drop_column("leads", "biz_date")
