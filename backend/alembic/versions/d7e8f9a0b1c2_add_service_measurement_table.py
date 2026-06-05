"""add service_measurements table (售后现场实测数据)

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "service_measurements" in sa_inspect(bind).get_table_names():
        return
    op.create_table(
        "service_measurements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("record_no", sa.String(64), nullable=False),
        sa.Column("ticket_id", sa.String(36), index=True),
        sa.Column("customer_id", sa.String(36), index=True),
        sa.Column("customer_name", sa.String(300)),
        sa.Column("service_date", sa.Date),
        sa.Column("engineer_id", sa.String(36)),
        sa.Column("engineer_name", sa.String(100)),
        sa.Column("industry", sa.String(32)),
        sa.Column("equipment_name", sa.String(200)),
        sa.Column("equipment_model", sa.String(120), index=True),
        sa.Column("product_no", sa.String(120)),
        sa.Column("motor_power_kw", sa.Numeric(10, 2)),
        sa.Column("amplitude_mm", sa.Numeric(8, 2)),
        sa.Column("material_name", sa.String(120)),
        sa.Column("layer_thickness_mm", sa.Numeric(10, 2)),
        sa.Column("feed_size_mm", sa.Numeric(10, 2)),
        sa.Column("screen_efficiency", sa.Numeric(6, 2)),
        sa.Column("throughput_tph", sa.Numeric(12, 2)),
        sa.Column("source_temp_c", sa.Numeric(6, 1)),
        sa.Column("ambient_temp_c", sa.Numeric(6, 1)),
        sa.Column("running_current_a", sa.Numeric(8, 2)),
        sa.Column("daily_run_hours", sa.Numeric(5, 1)),
        sa.Column("service_rating", sa.String(16)),
        sa.Column("product_rating", sa.String(16)),
        sa.Column("result_desc", sa.Text),
        sa.Column("issues", sa.Text),
        sa.Column("remark", sa.Text),
        sa.Column("created_by_id", sa.String(36)),
        sa.Column("created_by_name", sa.String(100)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    if "service_measurements" in sa_inspect(op.get_bind()).get_table_names():
        op.drop_table("service_measurements")
