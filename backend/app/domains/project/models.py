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
    competitors_json: Mapped[dict | None] = mapped_column(JSON)
    key_requirements_json: Mapped[dict | None] = mapped_column(JSON)
    risk_level: Mapped[str | None] = mapped_column(String(2))  # L/M/H
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/won/lost/suspended
    remark: Mapped[str | None] = mapped_column(Text)
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
