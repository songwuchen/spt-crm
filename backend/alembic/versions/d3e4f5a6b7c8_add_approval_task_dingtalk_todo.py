"""add dingtalk_todo_id to approval_tasks

审批任务推送到审批人的钉钉「待办」后，记录钉钉待办 id，便于任务被处理/取消时
回写完结该待办（避免钉钉待办里一直挂着已处理的审批）。

Revision ID: d3e4f5a6b7c8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d3e4f5a6b7c8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "approval_tasks" in insp.get_table_names() and not _has_column(insp, "approval_tasks", "dingtalk_todo_id"):
        op.add_column("approval_tasks", sa.Column("dingtalk_todo_id", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "approval_tasks", "dingtalk_todo_id"):
        op.drop_column("approval_tasks", "dingtalk_todo_id")
