from sqlalchemy import String, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ApprovalFlow(TenantScopedBase):
    """审批流主单 — 每次提交审批生成一条"""
    __tablename__ = "approval_flows"

    biz_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # quote_version / contract_version / change_request
    biz_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending / approved / rejected / withdrawn
    approval_mode: Mapped[str] = mapped_column(String(32), default="sequential")
    # sequential / parallel / any_one
    current_node: Mapped[int] = mapped_column(Integer, default=1)
    total_nodes: Mapped[int] = mapped_column(Integer, default=1)
    submitted_by_id: Mapped[str | None] = mapped_column(String(36))
    submitted_by_name: Mapped[str | None] = mapped_column(String(100))
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    parent_flow_id: Mapped[str | None] = mapped_column(String(36))
    revision_no: Mapped[int] = mapped_column(Integer, default=1)


class ApprovalTask(TenantScopedBase):
    """审批节点 — 每个审批人对应一条"""
    __tablename__ = "approval_tasks"

    flow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_order: Mapped[int] = mapped_column(Integer, default=1)
    assignee_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending / approved / rejected / waiting / cancelled
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[str | None] = mapped_column(String(30))
    dingtalk_todo_id: Mapped[str | None] = mapped_column(String(64))  # 关联钉钉个人待办 id，处理后回写完结
