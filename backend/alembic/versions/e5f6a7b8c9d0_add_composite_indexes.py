"""add composite indexes for high-frequency query paths

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # OpportunityProject: stage/status/owner filtering
    op.create_index('ix_opp_project_tenant_deleted_stage',
                    'opportunity_projects', ['tenant_id', 'is_deleted', 'stage_code'])
    op.create_index('ix_opp_project_tenant_owner',
                    'opportunity_projects', ['tenant_id', 'owner_id', 'is_deleted'])

    # PaymentPlan: overdue detection
    op.create_index('ix_payment_plan_tenant_status_due',
                    'payment_plans', ['tenant_id', 'status', 'due_date'])

    # AuditLog: primary query patterns
    op.create_index('ix_audit_log_tenant_resource_created',
                    'audit_logs', ['tenant_id', 'resource_type', 'created_at'])
    op.create_index('ix_audit_log_tenant_user_created',
                    'audit_logs', ['tenant_id', 'user_id', 'created_at'])

    # ApprovalFlow: duplicate prevention + SLA checks
    op.create_index('ix_approval_flow_biz_status',
                    'approval_flows', ['tenant_id', 'biz_type', 'biz_id', 'status'])

    # ApprovalTask: user pending approvals
    op.create_index('ix_approval_task_assignee_status',
                    'approval_tasks', ['tenant_id', 'assignee_id', 'status'])

    # AiTask: business entity lookup
    op.create_index('ix_ai_task_tenant_biz',
                    'ai_tasks', ['tenant_id', 'biz_type', 'biz_id'])


def downgrade() -> None:
    op.drop_index('ix_ai_task_tenant_biz', table_name='ai_tasks')
    op.drop_index('ix_approval_task_assignee_status', table_name='approval_tasks')
    op.drop_index('ix_approval_flow_biz_status', table_name='approval_flows')
    op.drop_index('ix_audit_log_tenant_user_created', table_name='audit_logs')
    op.drop_index('ix_audit_log_tenant_resource_created', table_name='audit_logs')
    op.drop_index('ix_payment_plan_tenant_status_due', table_name='payment_plans')
    op.drop_index('ix_opp_project_tenant_owner', table_name='opportunity_projects')
    op.drop_index('ix_opp_project_tenant_deleted_stage', table_name='opportunity_projects')
