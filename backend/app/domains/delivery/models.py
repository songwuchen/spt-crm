from sqlalchemy import String, Text, JSON, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ErpOrderLink(TenantScopedBase):
    """Maps a CRM project to an ERP order number."""
    __tablename__ = "erp_order_links"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    erp_system_code: Mapped[str | None] = mapped_column(String(64))
    erp_order_no: Mapped[str | None] = mapped_column(String(100))
    sync_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/synced/failed
    remark: Mapped[str | None] = mapped_column(String(500))


class DeliveryMilestone(TenantScopedBase):
    """Tracks delivery milestones for a project."""
    __tablename__ = "delivery_milestones"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    milestone_code: Mapped[str] = mapped_column(String(32), nullable=False)
    # design/procure/produce/fat/ship/install/sat/accept
    name: Mapped[str | None] = mapped_column(String(200))
    plan_date: Mapped[str | None] = mapped_column(Date)
    actual_date: Mapped[str | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="not_start")
    # not_start/doing/done/delayed
    source_type: Mapped[str] = mapped_column(String(16), default="manual")
    # manual/erp/mes
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)
