"""Add code_sequences table for unified document number generation.

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "y6z7a8b9c0d1"
down_revision = "x5y6z7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa_inspect(conn)
    if "code_sequences" not in insp.get_table_names():
        op.create_table(
            "code_sequences",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("prefix", sa.String(16), nullable=False),
            sa.Column("date_key", sa.String(8), nullable=False),
            sa.Column("current_seq", sa.Integer, nullable=False, server_default="0"),
        )
        op.create_index(
            "ix_code_sequences_lookup",
            "code_sequences",
            ["tenant_id", "prefix", "date_key"],
            unique=True,
        )


def downgrade():
    op.drop_table("code_sequences")
