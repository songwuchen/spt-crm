from sqlalchemy import String, Text, JSON, Integer, Numeric, Date, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase, utcnow


class OpportunityProject(TenantScopedBase):
    __tablename__ = "opportunity_projects"

    project_code: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    stage_code: Mapped[str] = mapped_column(String(16), default="S1")
    amount_expect: Mapped[float | None] = mapped_column(Numeric(18, 2))
    probability: Mapped[int | None] = mapped_column(Integer)
    close_date_expect: Mapped[str | None] = mapped_column(Date)
    # 业务日期：用户可自行编辑，用于标识不同时间的商机（区别于 created_at 与预计成交日）(issue #84)
    biz_date: Mapped[str | None] = mapped_column(Date)
    competitors_json: Mapped[dict | None] = mapped_column(JSON)
    key_requirements_json: Mapped[dict | None] = mapped_column(JSON)
    risk_level: Mapped[str | None] = mapped_column(String(2))  # L/M/H
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    # 录入人（创建人）— 与负责人分家：负责人可被主管转移，录入人永久保留以供溯源
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/won/lost/suspended
    remark: Mapped[str | None] = mapped_column(Text)
    # Business-specific flags (issue #18)
    has_guarantee: Mapped[bool | None] = mapped_column(Boolean)
    has_weight_requirement: Mapped[bool | None] = mapped_column(Boolean)
    uses_idle_equipment: Mapped[bool | None] = mapped_column(Boolean)
    payment_method: Mapped[str | None] = mapped_column(String(64))
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ProjectStageHistory(TenantScopedBase):
    __tablename__ = "project_stage_history"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_stage: Mapped[str] = mapped_column(String(16), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(16), nullable=False)
    changed_by_id: Mapped[str | None] = mapped_column(String(36))
    changed_by_name: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)


class ProjectMember(TenantScopedBase):
    """商机团队成员：支持多部门、多人协作。一个商机可有多名成员，
    各自带角色(售前/商务/交付/财务/项目经理)、所属部门与读写权限。"""
    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_name: Mapped[str | None] = mapped_column(String(100))
    member_role: Mapped[str | None] = mapped_column(String(32))  # presale/business/delivery/finance/pm
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(100))
    permission: Mapped[str] = mapped_column(String(16), default="view")  # view/edit
    added_by_id: Mapped[str | None] = mapped_column(String(36))
    added_by_name: Mapped[str | None] = mapped_column(String(100))
