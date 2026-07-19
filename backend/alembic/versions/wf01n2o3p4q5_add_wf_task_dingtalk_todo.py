"""add dingtalk_todo_id to wf_task_instance

新工作流引擎补齐通知层：待办下发到审批人的钉钉「待办」后记录钉钉待办 id，
便于待办被处理/作废/转交时回写完结（对齐旧引擎 approval_tasks.dingtalk_todo_id）。

Revision ID: wf01n2o3p4q5
Revises: fp01a2b3c4d5
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "wf01n2o3p4q5"
down_revision = "fp01a2b3c4d5"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "wf_task_instance" in insp.get_table_names() and not _has_column(insp, "wf_task_instance", "dingtalk_todo_id"):
        op.add_column("wf_task_instance", sa.Column("dingtalk_todo_id", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "wf_task_instance", "dingtalk_todo_id"):
        op.drop_column("wf_task_instance", "dingtalk_todo_id")
