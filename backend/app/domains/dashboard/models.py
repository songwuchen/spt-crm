from sqlalchemy import String, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class SalesTarget(TenantScopedBase):
    __tablename__ = "sales_targets"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_name: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    target_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    target_count: Mapped[int | None] = mapped_column(Integer)  # optional: target deal count
