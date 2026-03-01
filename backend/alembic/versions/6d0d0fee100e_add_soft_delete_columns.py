"""add_soft_delete_columns

Revision ID: 6d0d0fee100e
Revises: 4309d75755b8
Create Date: 2026-02-28 17:41:54.099509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d0d0fee100e'
down_revision: Union[str, None] = '4309d75755b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns with server_default so existing rows get False
    op.add_column('customers', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index(op.f('ix_customers_is_deleted'), 'customers', ['is_deleted'], unique=False)
    op.add_column('leads', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index(op.f('ix_leads_is_deleted'), 'leads', ['is_deleted'], unique=False)
    op.add_column('opportunity_projects', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index(op.f('ix_opportunity_projects_is_deleted'), 'opportunity_projects', ['is_deleted'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_opportunity_projects_is_deleted'), table_name='opportunity_projects')
    op.drop_column('opportunity_projects', 'is_deleted')
    op.drop_index(op.f('ix_leads_is_deleted'), table_name='leads')
    op.drop_column('leads', 'is_deleted')
    op.drop_index(op.f('ix_customers_is_deleted'), table_name='customers')
    op.drop_column('customers', 'is_deleted')
