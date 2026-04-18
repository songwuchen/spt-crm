from sqlalchemy import String, Integer, Numeric, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.database import TenantScopedBase


class SalesTarget(TenantScopedBase):
    __tablename__ = "sales_targets"

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(200))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    target_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    target_count: Mapped[int | None] = mapped_column(Integer)  # optional: target deal count


class DashboardSnapshot(TenantScopedBase):
    __tablename__ = "dashboard_snapshots"

    share_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON blob of dashboard data
    card_visibility_json: Mapped[str | None] = mapped_column(Text)  # card visibility config
    card_order_json: Mapped[str | None] = mapped_column(Text)  # card order config
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
