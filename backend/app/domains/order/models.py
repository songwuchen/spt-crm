from sqlalchemy import String, Text, Numeric, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Order(TenantScopedBase):
    """订单：客户的成交订单，可关联商机与合同。"""
    __tablename__ = "orders"

    order_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    contract_id: Mapped[str | None] = mapped_column(String(36), index=True)
    title: Mapped[str | None] = mapped_column(String(300))
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    # draft/confirmed/producing/shipped/completed/cancelled
    order_date: Mapped[str | None] = mapped_column(Date)
    delivery_date: Mapped[str | None] = mapped_column(Date)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
