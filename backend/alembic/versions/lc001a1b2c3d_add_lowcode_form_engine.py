"""add lowcode form engine tables (Phase 0)

扩展平台表单引擎: lc_form_template / lc_form_template_version /
lc_form_instance / lc_form_instance_detail_row / lc_serial_counter。
纯新增表,不改动既有业务表,可安全前滚/回滚。

Revision ID: lc001a1b2c3d
Revises: d3e4f5a6b7c8
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "lc001a1b2c3d"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lc_form_template",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("icon", sa.String(128), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("deleted_fields", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_lc_form_template_tenant_code", "lc_form_template", ["tenant_id", "code"], unique=True)

    op.create_table(
        "lc_form_template_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("template_id", sa.String(36), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("field_definitions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("layout_definition", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("rule_definitions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lc_form_instance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("template_version_id", sa.String(36), nullable=False),
        sa.Column("process_instance_id", sa.String(36), nullable=True),
        sa.Column("business_no", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("initiator_id", sa.String(36), nullable=False),
        sa.Column("initiator_dept_id", sa.String(36), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("app_id", sa.String(36), nullable=True),
        sa.Column("form_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("field_definitions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("share_token", sa.String(64), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lc_form_instance_template_id", "lc_form_instance", ["template_id"])
    op.create_index("ix_lc_form_instance_initiator", "lc_form_instance", ["initiator_id", "status"])
    op.create_index("ix_lc_form_instance_business_no", "lc_form_instance", ["business_no"])
    op.create_index("ix_lc_form_instance_status", "lc_form_instance", ["status"])
    op.create_index("ix_lc_form_instance_tpl_created", "lc_form_instance", ["tenant_id", "template_id", "created_at"])
    op.create_index("ix_lc_form_instance_share_token", "lc_form_instance", ["share_token"], unique=True)
    op.create_index(
        "ix_lc_form_instance_deleted_at", "lc_form_instance", ["deleted_at"],
        postgresql_where=sa.text("is_deleted"),
    )

    op.create_table(
        "lc_form_instance_detail_row",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("form_instance_id", sa.String(36), nullable=False, index=True),
        sa.Column("field_key", sa.String(64), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("row_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lc_serial_counter",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("field_id", sa.String(64), nullable=False),
        sa.Column("period_key", sa.String(32), nullable=False, server_default=""),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_lc_serial_counter", "lc_serial_counter", ["tenant_id", "template_id", "field_id", "period_key"], unique=True)


def downgrade():
    op.drop_table("lc_serial_counter")
    op.drop_table("lc_form_instance_detail_row")
    op.drop_index("ix_lc_form_instance_deleted_at", table_name="lc_form_instance")
    op.drop_index("ix_lc_form_instance_share_token", table_name="lc_form_instance")
    op.drop_index("ix_lc_form_instance_tpl_created", table_name="lc_form_instance")
    op.drop_index("ix_lc_form_instance_status", table_name="lc_form_instance")
    op.drop_index("ix_lc_form_instance_business_no", table_name="lc_form_instance")
    op.drop_index("ix_lc_form_instance_initiator", table_name="lc_form_instance")
    op.drop_index("ix_lc_form_instance_template_id", table_name="lc_form_instance")
    op.drop_table("lc_form_instance")
    op.drop_table("lc_form_template_version")
    op.drop_index("uq_lc_form_template_tenant_code", table_name="lc_form_template")
    op.drop_table("lc_form_template")
