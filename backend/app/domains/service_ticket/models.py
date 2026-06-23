from sqlalchemy import String, Text, JSON, Integer, Numeric, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ServiceTicket(TenantScopedBase):
    __tablename__ = "service_tickets"

    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    order_id: Mapped[str | None] = mapped_column(String(36), index=True)  # 关联客户订单，快速获取产品信息
    ticket_no: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # fault/maintenance/training/spare/upgrade
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    # low/medium/high/critical
    status: Mapped[str] = mapped_column(String(16), default="open")
    # open/assigned/in_progress/resolved/closed
    description: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    ai_summary_json: Mapped[dict | None] = mapped_column(JSON)
    assigned_to_id: Mapped[str | None] = mapped_column(String(36))
    assigned_to_name: Mapped[str | None] = mapped_column(String(100))
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    # SLA fields
    sla_respond_by: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    sla_resolve_by: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    sla_responded_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    sla_resolved_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    # Satisfaction
    satisfaction_score: Mapped[int | None] = mapped_column(Integer)  # 1-5 stars
    satisfaction_comment: Mapped[str | None] = mapped_column(Text)
    satisfaction_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class RenewalOpportunity(TenantScopedBase):
    __tablename__ = "renewal_opportunities"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_expect: Mapped[float | None] = mapped_column(Numeric(18, 2))
    close_date_expect: Mapped[str | None] = mapped_column(Date)
    probability: Mapped[int | None] = mapped_column(Integer)
    related_asset_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open/won/lost
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text)
