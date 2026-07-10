"""add lead review workflow fields (review_status/review_flow_id/reject_reason)

线索提交审核流程：业务员提交的线索需信息情报部内勤审核，内勤自身录入/导入免审。
新增字段承载审核态：
  - review_status: approved(默认/免审/审核通过) / pending(待审核) / rejected(已驳回)
  - review_flow_id: 关联的审批流 id（approval_flows.id）
  - reject_reason: 最近一次驳回原因

存量数据一律置为 approved（视为已通过），不影响既有线索可用性。

Revision ID: d2e3f4a5b6c7
Revises: c3d4e5f6a7b1
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d2e3f4a5b6c7"
down_revision = "c3d4e5f6a7b1"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "leads" not in insp.get_table_names():
        return

    if not _has_column(insp, "leads", "review_status"):
        op.add_column(
            "leads",
            sa.Column("review_status", sa.String(20), nullable=False, server_default="approved"),
        )
        op.create_index("ix_leads_review_status", "leads", ["review_status"])
    if not _has_column(insp, "leads", "review_flow_id"):
        op.add_column("leads", sa.Column("review_flow_id", sa.String(36), nullable=True))
    if not _has_column(insp, "leads", "reject_reason"):
        op.add_column("leads", sa.Column("reject_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if _has_column(insp, "leads", "reject_reason"):
        op.drop_column("leads", "reject_reason")
    if _has_column(insp, "leads", "review_flow_id"):
        op.drop_column("leads", "review_flow_id")
    if _has_column(insp, "leads", "review_status"):
        if "ix_leads_review_status" in {i["name"] for i in insp.get_indexes("leads")}:
            op.drop_index("ix_leads_review_status", "leads")
        op.drop_column("leads", "review_status")
