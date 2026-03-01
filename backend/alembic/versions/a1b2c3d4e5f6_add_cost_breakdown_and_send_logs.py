"""add_cost_breakdown_and_send_logs

Revision ID: a1b2c3d4e5f6
Revises: 6d0d0fee100e
Create Date: 2026-03-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6d0d0fee100e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add breakdown_json to cost_snapshots
    op.add_column('cost_snapshots', sa.Column('breakdown_json', sa.JSON(), nullable=True))

    # Create quote_send_logs table
    op.create_table('quote_send_logs',
        sa.Column('quote_id', sa.String(36), nullable=False),
        sa.Column('quote_version_id', sa.String(36), nullable=False),
        sa.Column('channel', sa.String(32), nullable=False),
        sa.Column('to_list_json', sa.JSON(), nullable=True),
        sa.Column('subject', sa.String(300), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('attachments_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='sent'),
        sa.Column('sent_by_id', sa.String(36), nullable=True),
        sa.Column('sent_by_name', sa.String(100), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quote_send_logs_quote_id', 'quote_send_logs', ['quote_id'])
    op.create_index('ix_quote_send_logs_quote_version_id', 'quote_send_logs', ['quote_version_id'])
    op.create_index('ix_quote_send_logs_tenant_id', 'quote_send_logs', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_quote_send_logs_tenant_id')
    op.drop_index('ix_quote_send_logs_quote_version_id')
    op.drop_index('ix_quote_send_logs_quote_id')
    op.drop_table('quote_send_logs')
    op.drop_column('cost_snapshots', 'breakdown_json')
