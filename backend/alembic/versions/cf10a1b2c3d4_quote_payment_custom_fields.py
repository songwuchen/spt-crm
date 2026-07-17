"""add custom_fields_json to quotes/payment_records

为 quotes / payment_records 增加 custom_fields_json(JSON, 可空),使报价、回款也能
配置并存储扩展平台自定义字段(与 leads/orders/... 对齐)。纯新增列,安全前滚/回滚。

Revision ID: cf10a1b2c3d4
Revises: be1c2d3e4f60
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "cf10a1b2c3d4"
down_revision = "be1c2d3e4f60"
branch_labels = None
depends_on = None

_TABLES = ["quotes", "payment_records"]


def upgrade():
    for t in _TABLES:
        op.add_column(t, sa.Column("custom_fields_json", sa.JSON(), nullable=True))


def downgrade():
    for t in _TABLES:
        op.drop_column(t, "custom_fields_json")
