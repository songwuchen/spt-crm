from sqlalchemy import String, Text, JSON, Integer, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ProductCategory(TenantScopedBase):
    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(500))


class Product(TenantScopedBase):
    __tablename__ = "products"

    product_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(36), index=True)
    item_type: Mapped[str | None] = mapped_column(String(16))  # standard/nonstandard/service/spare
    spec: Mapped[str | None] = mapped_column(String(500))
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    cost_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    leadtime_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str | None] = mapped_column(Text)
    extra_json: Mapped[dict | None] = mapped_column(JSON)
