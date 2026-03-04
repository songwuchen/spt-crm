"""enhance approval system: add approval_mode, escalation, resubmit fields

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch A: approval_mode on approval_flows
    op.add_column('approval_flows', sa.Column('approval_mode', sa.String(32), server_default='sequential', nullable=False))

    # Batch C: escalation_json on approval_policies, escalation_level on approval_flows
    op.add_column('approval_policies', sa.Column('escalation_json', sa.JSON(), nullable=True))
    op.add_column('approval_flows', sa.Column('escalation_level', sa.Integer(), server_default='0', nullable=False))

    # Batch D: parent_flow_id and revision_no on approval_flows
    op.add_column('approval_flows', sa.Column('parent_flow_id', sa.String(36), nullable=True))
    op.add_column('approval_flows', sa.Column('revision_no', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('approval_flows', 'revision_no')
    op.drop_column('approval_flows', 'parent_flow_id')
    op.drop_column('approval_flows', 'escalation_level')
    op.drop_column('approval_policies', 'escalation_json')
    op.drop_column('approval_flows', 'approval_mode')
