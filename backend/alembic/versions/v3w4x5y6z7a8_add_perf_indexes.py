"""add performance indexes for approval flow and analytics

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-03-11
"""
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    # Composite index on approval_flows(tenant_id, status) for fast pending lookups
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("approval_flows")} if "approval_flows" in inspector.get_table_names() else set()

    if "ix_approval_flow_tenant_status" not in existing_indexes:
        op.create_index("ix_approval_flow_tenant_status", "approval_flows", ["tenant_id", "status"])

    if "ix_approval_flow_biz" not in existing_indexes:
        op.create_index("ix_approval_flow_biz", "approval_flows", ["tenant_id", "biz_type", "status"])

    # Index on opportunity_projects for analytics queries
    existing_proj_indexes = {idx["name"] for idx in inspector.get_indexes("opportunity_projects")} if "opportunity_projects" in inspector.get_table_names() else set()

    if "ix_project_tenant_stage_status" not in existing_proj_indexes:
        op.create_index("ix_project_tenant_stage_status", "opportunity_projects", ["tenant_id", "stage_code", "status"])

    # Index on knowledge_chunks for RAG search
    existing_chunk_indexes = {idx["name"] for idx in inspector.get_indexes("knowledge_chunks")} if "knowledge_chunks" in inspector.get_table_names() else set()

    if "ix_knowledge_chunk_doc_idx" not in existing_chunk_indexes:
        op.create_index("ix_knowledge_chunk_doc_idx", "knowledge_chunks", ["document_id", "chunk_index"])


def downgrade():
    op.drop_index("ix_knowledge_chunk_doc_idx", table_name="knowledge_chunks")
    op.drop_index("ix_project_tenant_stage_status", table_name="opportunity_projects")
    op.drop_index("ix_approval_flow_biz", table_name="approval_flows")
    op.drop_index("ix_approval_flow_tenant_status", table_name="approval_flows")
