"""add outbox inbox events

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('aggregate_type', sa.String(64), nullable=False, index=True),
        sa.Column('aggregate_id', sa.String(36), nullable=False, index=True),
        sa.Column('payload_json', sa.JSON, nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending', index=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('published_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'inbox_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, index=True),
        sa.Column('source', sa.String(100), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('external_id', sa.String(200), nullable=True, index=True),
        sa.Column('payload_json', sa.JSON, nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='received', index=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('processed_at', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table('inbox_events')
    op.drop_table('outbox_events')
