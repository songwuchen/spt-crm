from sqlalchemy import String, Text, Numeric, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Tender(TenantScopedBase):
    """标书：客户的投标/招标项目，可关联商机。"""
    __tablename__ = "tenders"

    tender_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    bid_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    budget_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(16), default="preparing")
    # preparing/submitted/won/lost/cancelled
    submit_date: Mapped[str | None] = mapped_column(Date)
    open_date: Mapped[str | None] = mapped_column(Date)
    result: Mapped[str | None] = mapped_column(String(300))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
