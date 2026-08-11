"""add tech_agreement_reviews table (合同技术协议评审)

Revision ID: tar01a2b3c4d5
Revises: ps01a2b3c4d5
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "tar01a2b3c4d5"
down_revision = "ps01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "tech_agreement_reviews" in inspector.get_table_names():
        return
    op.create_table(
        "tech_agreement_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("review_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft"),
        sa.Column("customer_id", sa.String(36)),
        sa.Column("company_name", sa.String(300)),
        sa.Column("applicant_id", sa.String(36)),
        sa.Column("applicant_name", sa.String(100)),
        sa.Column("apply_at", sa.DateTime(timezone=True)),
        sa.Column("owner_id", sa.String(36)),
        sa.Column("owner_name", sa.String(100)),
        sa.Column("department_id", sa.String(36)),
        sa.Column("department_name", sa.String(200)),
        sa.Column("industry", sa.String(200)),
        sa.Column("address", sa.String(500)),
        sa.Column("elec_ctrl", sa.String(64)),
        sa.Column("project_title", sa.Text()),
        sa.Column("has_weight_req", sa.String(16)),
        sa.Column("use_idle_equip", sa.String(16)),
        sa.Column("has_smart", sa.String(16)),
        sa.Column("need_pricing", sa.String(32)),
        sa.Column("sign_basis", sa.String(500)),
        sa.Column("ref_contract_no", sa.String(200)),
        sa.Column("pre_contact", sa.String(200)),
        sa.Column("remark", sa.Text()),
        sa.Column("has_objection", sa.String(16)),
        sa.Column("form_json", sa.JSON()),
        sa.Column("created_by_id", sa.String(36)),
        sa.Column("created_by_name", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tar_review_code", "tech_agreement_reviews", ["review_code"])
    op.create_index("ix_tar_status", "tech_agreement_reviews", ["status"])
    op.create_index("ix_tar_customer_id", "tech_agreement_reviews", ["customer_id"])
    op.create_index("ix_tar_owner_id", "tech_agreement_reviews", ["owner_id"])
    op.create_index("ix_tar_tenant_status", "tech_agreement_reviews", ["tenant_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    if "tech_agreement_reviews" in sa_inspect(bind).get_table_names():
        op.drop_table("tech_agreement_reviews")
