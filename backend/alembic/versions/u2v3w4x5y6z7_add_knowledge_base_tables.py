"""add knowledge base tables

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    if "knowledge_documents" not in existing:
        op.create_table(
            "knowledge_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("doc_type", sa.String(32), nullable=False, index=True),
            sa.Column("source_filename", sa.String(500)),
            sa.Column("content_text", sa.Text),
            sa.Column("metadata_json", sa.JSON),
            sa.Column("chunk_count", sa.Integer, default=0),
            sa.Column("status", sa.String(16), default="active", index=True),
            sa.Column("created_by_id", sa.String(36)),
            sa.Column("created_by_name", sa.String(100)),
            sa.Column("is_deleted", sa.Boolean, default=False, index=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )

    if "knowledge_chunks" not in existing:
        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("document_id", sa.String(36), nullable=False, index=True),
            sa.Column("chunk_index", sa.Integer, nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("token_count", sa.Integer, default=0),
            sa.Column("metadata_json", sa.JSON),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        )


def downgrade():
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
