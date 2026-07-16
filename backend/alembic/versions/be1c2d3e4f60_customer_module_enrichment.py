"""customer module enrichment: BANT/intent snapshot, follow-up denorm, multi-pool, enriched profile

客户模块产品完善（三阶段）落库：
- 商机要素/采购意向快照：intent_level / key_contact_id / demand / need_match_level /
  budget_amount / expected_purchase_date / headcount
- 公司档案增补：industry_l1/l2/l3 / country / postal_code / currency
- 归属/审计增补：department_id/name / updated_by_id/name
- 跟进&公海生命周期冗余：last_activity_at/by / won_deal_count / pool_id / pool_source / pool_entered_at
- 新增区域公海表 customer_pools

Revision ID: be1c2d3e4f60
Revises: ad01f2e3d4c5
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "be1c2d3e4f60"
down_revision = "ad01f2e3d4c5"
branch_labels = None
depends_on = None


# (name, column) — 全部可空/带默认，纯增列，回填历史数据后续在 service 层惰性完成
_CUSTOMER_COLUMNS = [
    ("intent_level", sa.Column("intent_level", sa.String(length=10), nullable=True)),
    ("key_contact_id", sa.Column("key_contact_id", sa.String(length=36), nullable=True)),
    ("demand", sa.Column("demand", sa.Text(), nullable=True)),
    ("need_match_level", sa.Column("need_match_level", sa.String(length=32), nullable=True)),
    ("budget_amount", sa.Column("budget_amount", sa.Numeric(18, 2), nullable=True)),
    ("expected_purchase_date", sa.Column("expected_purchase_date", sa.Date(), nullable=True)),
    ("headcount", sa.Column("headcount", sa.Integer(), nullable=True)),
    ("industry_l1", sa.Column("industry_l1", sa.String(length=100), nullable=True)),
    ("industry_l2", sa.Column("industry_l2", sa.String(length=100), nullable=True)),
    ("industry_l3", sa.Column("industry_l3", sa.String(length=100), nullable=True)),
    ("country", sa.Column("country", sa.String(length=50), nullable=True)),
    ("postal_code", sa.Column("postal_code", sa.String(length=20), nullable=True)),
    ("currency", sa.Column("currency", sa.String(length=10), nullable=True)),
    ("department_id", sa.Column("department_id", sa.String(length=36), nullable=True)),
    ("department_name", sa.Column("department_name", sa.String(length=100), nullable=True)),
    ("updated_by_id", sa.Column("updated_by_id", sa.String(length=36), nullable=True)),
    ("updated_by_name", sa.Column("updated_by_name", sa.String(length=100), nullable=True)),
    ("last_activity_at", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True)),
    ("last_activity_by_id", sa.Column("last_activity_by_id", sa.String(length=36), nullable=True)),
    ("last_activity_by_name", sa.Column("last_activity_by_name", sa.String(length=100), nullable=True)),
    ("won_deal_count", sa.Column("won_deal_count", sa.Integer(), nullable=False, server_default="0")),
    ("pool_id", sa.Column("pool_id", sa.String(length=36), nullable=True)),
    ("pool_source", sa.Column("pool_source", sa.String(length=32), nullable=True)),
    ("pool_entered_at", sa.Column("pool_entered_at", sa.DateTime(timezone=True), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    existing = {c["name"] for c in insp.get_columns("customers")}
    for name, col in _CUSTOMER_COLUMNS:
        if name not in existing:
            op.add_column("customers", col)

    idx = {i["name"] for i in insp.get_indexes("customers")}
    if "ix_customers_last_activity_at" not in idx:
        op.create_index("ix_customers_last_activity_at", "customers", ["last_activity_at"], unique=False)
    if "ix_customers_pool_id" not in idx:
        op.create_index("ix_customers_pool_id", "customers", ["pool_id"], unique=False)

    # 回填冗余：结单商机数 + 最新活动时间（存量客户即刻可见）
    op.execute(
        "UPDATE customers SET won_deal_count = COALESCE(("
        " SELECT COUNT(*) FROM opportunity_projects p"
        " WHERE p.customer_id = customers.id AND p.status = 'won'), 0)"
    )
    op.execute(
        "UPDATE customers SET last_activity_at = ("
        " SELECT MAX(a.created_at) FROM activities a"
        " WHERE a.biz_type = 'customer' AND a.biz_id = customers.id)"
        " WHERE last_activity_at IS NULL"
    )

    if not insp.has_table("customer_pools"):
        op.create_table(
            "customer_pools",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=300), nullable=True),
            sa.Column("region_scope", sa.String(length=300), nullable=True),
            sa.Column("rules_json", sa.JSON(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_customer_pools_tenant_id", "customer_pools", ["tenant_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if insp.has_table("customer_pools"):
        op.drop_index("ix_customer_pools_tenant_id", table_name="customer_pools")
        op.drop_table("customer_pools")

    idx = {i["name"] for i in insp.get_indexes("customers")}
    if "ix_customers_pool_id" in idx:
        op.drop_index("ix_customers_pool_id", table_name="customers")
    if "ix_customers_last_activity_at" in idx:
        op.drop_index("ix_customers_last_activity_at", table_name="customers")

    existing = {c["name"] for c in insp.get_columns("customers")}
    for name, _col in reversed(_CUSTOMER_COLUMNS):
        if name in existing:
            op.drop_column("customers", name)
