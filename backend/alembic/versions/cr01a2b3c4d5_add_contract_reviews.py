"""add contract_reviews table (合同评审)

Revision ID: cr01a2b3c4d5
Revises: ct02b3c4d5e6
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "cr01a2b3c4d5"
down_revision = "ct02b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "contract_reviews" in inspector.get_table_names():
        return
    op.create_table(
        "contract_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("review_code", sa.String(64), nullable=False),
        sa.Column("review_type", sa.String(32)),
        sa.Column("status", sa.String(24), server_default="draft"),
        sa.Column("customer_id", sa.String(36)),
        sa.Column("company_name", sa.String(300)),
        sa.Column("owner_id", sa.String(36)),
        sa.Column("owner_name", sa.String(100)),
        sa.Column("department_id", sa.String(36)),
        sa.Column("department_name", sa.String(200)),
        sa.Column("region_manager_id", sa.String(36)),
        sa.Column("region_manager_name", sa.String(100)),
        sa.Column("is_export", sa.String(16)),
        sa.Column("need_pricing", sa.String(32)),
        sa.Column("need_install", sa.String(64)),
        sa.Column("customer_type", sa.String(32)),
        sa.Column("elec_ctrl", sa.String(64)),
        sa.Column("project_title", sa.Text()),
        sa.Column("reported_at", sa.DateTime(timezone=True)),
        sa.Column("contract_amount", sa.Numeric(18, 2)),
        sa.Column("delivery_period", sa.String(200)),
        sa.Column("conclusion", sa.Text()),
        sa.Column("payment_term", sa.String(200)),
        sa.Column("review_json", sa.JSON()),
        sa.Column("created_by_id", sa.String(36)),
        sa.Column("created_by_name", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_contract_reviews_review_code", "contract_reviews", ["review_code"])
    op.create_index("ix_contract_reviews_status", "contract_reviews", ["status"])
    op.create_index("ix_contract_reviews_customer_id", "contract_reviews", ["customer_id"])
    op.create_index("ix_contract_reviews_owner_id", "contract_reviews", ["owner_id"])
    op.create_index("ix_cr_tenant_status", "contract_reviews", ["tenant_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    if "contract_reviews" in sa_inspect(bind).get_table_names():
        op.drop_table("contract_reviews")
