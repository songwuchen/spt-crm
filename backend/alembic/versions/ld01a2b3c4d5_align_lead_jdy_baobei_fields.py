"""align leads with JDY 销售中心「申报信息」fields

Revision ID: ld01a2b3c4d5
Revises: cu01a2b3c4d5
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ld01a2b3c4d5"
down_revision = "cu01a2b3c4d5"
branch_labels = None
depends_on = None

_LEAD_COLUMNS = [
    ("has_internal_conflict", sa.Column("has_internal_conflict", sa.String(10), nullable=True)),
    ("conflict_note", sa.Column("conflict_note", sa.String(500), nullable=True)),
    ("bid_result", sa.Column("bid_result", sa.String(50), nullable=True)),
    ("bid_fail_reason", sa.Column("bid_fail_reason", sa.String(500), nullable=True)),
    ("entrust_status", sa.Column("entrust_status", sa.String(20), nullable=True)),
    ("entrust_issued_at", sa.Column("entrust_issued_at", sa.DateTime(timezone=True), nullable=True)),
    ("entrust_term", sa.Column("entrust_term", sa.String(100), nullable=True)),
    ("project_activity", sa.Column("project_activity", sa.String(50), nullable=True)),
    ("project_recent", sa.Column("project_recent", sa.String(500), nullable=True)),
    ("follow_progress", sa.Column("follow_progress", sa.String(500), nullable=True)),
    ("site_visit", sa.Column("site_visit", sa.String(500), nullable=True)),
    ("report_project_status", sa.Column("report_project_status", sa.String(50), nullable=True)),
    ("assess_remark", sa.Column("assess_remark", sa.Text(), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    existing = {c["name"] for c in insp.get_columns("leads")}
    for name, col in _LEAD_COLUMNS:
        if name not in existing:
            op.add_column("leads", col)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    existing = {c["name"] for c in insp.get_columns("leads")}
    for name, _ in reversed(_LEAD_COLUMNS):
        if name in existing:
            op.drop_column("leads", name)
