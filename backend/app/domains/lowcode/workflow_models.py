"""扩展平台 — 可视化审批流程引擎数据模型(wf_*)。

移植自 spt-lowcode app/models/workflow/*,适配 CRM(String(36) 主键/租户、TenantScopedBase)。
设计要点:
- 定义与运行分离: wf_process_definition(+version) 冻结节点/连线/审批人规则(JSONB);
  运行时 wf_process_instance/node_instance/task_instance 独立,流程模板改版不影响在途实例。
- 待办为独立任务实例(wf_task_instance),不临时按状态算,保证一致性与性能。
- 分支挂在连线(route_definitions.condition)上;并行汇聚用 pending_joins(AND-join)记账。
DingTalk OA 集成相关列/表 MVP 暂略(CRM 另有 dingtalk_sync,后续按需接入)。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


# ==================== 流程定义 ====================

class WfProcessDefinition(TenantScopedBase):
    __tablename__ = "wf_process_definition"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 绑定的表单模板(自定义表单)或既有业务 biz_type(替换旧审批引擎时用)。
    form_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    biz_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("uq_wf_process_definition_tenant_code", "tenant_id", "code", unique=True),
    )


class WfProcessDefinitionVersion(TenantScopedBase):
    __tablename__ = "wf_process_definition_version"

    process_definition_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_definitions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    route_definitions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    approver_rules: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    form_template_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


# ==================== 流程运行 ====================

class WfProcessInstance(TenantScopedBase):
    __tablename__ = "wf_process_instance"

    process_definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    process_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    form_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 替换旧审批引擎时,承载既有业务单据: (biz_type, biz_id)。
    biz_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    biz_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    business_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initiator_id: Mapped[str] = mapped_column(String(36), nullable=False)
    initiator_dept_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parent_process_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parent_node_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    # 发起人自选审批人: {node_def_id: [user_id, ...]}
    nominated_approvers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 并行汇聚(AND-join)等待中的目标节点 def_id 列表。
    pending_joins: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_wf_process_instance_initiator", "initiator_id", "status"),
        Index("ix_wf_process_instance_status", "status"),
        Index("ix_wf_process_instance_biz", "biz_type", "biz_id"),
    )


class WfNodeInstance(TenantScopedBase):
    __tablename__ = "wf_node_instance"

    process_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_def_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    node_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WfTaskInstance(TenantScopedBase):
    """待办任务实例(独立概念,不临时按流程状态算)。"""
    __tablename__ = "wf_task_instance"

    process_instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    node_instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    assignee_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 乐观锁,防并发重复审批
    task_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 顺序会签用

    __table_args__ = (
        Index("ix_wf_task_assignee_status", "assignee_id", "status"),
        Index("ix_wf_task_process_instance", "process_instance_id"),
        Index("ix_wf_task_node_instance", "node_instance_id"),
    )


class WfTaskActionLog(TenantScopedBase):
    """任务动作留痕(提交/通过/驳回/转交/加签/撤回...)。"""
    __tablename__ = "wf_task_action_log"

    process_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class WfProcessComment(TenantScopedBase):
    __tablename__ = "wf_process_comment"

    process_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class WfProcessCc(TenantScopedBase):
    """抄送记录(读/未读)。"""
    __tablename__ = "wf_process_cc"

    process_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))

    __table_args__ = (
        Index("ix_wf_process_cc_user", "user_id", "is_read"),
    )
