from sqlalchemy import String, Text, Numeric, Date, Boolean, Integer, JSON
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
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 扩展平台自定义字段
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))  # 合计金额（有明细时由明细汇总）
    currency: Mapped[str | None] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    # draft/confirmed/producing/shipped/completed/cancelled
    order_date: Mapped[str | None] = mapped_column(Date)
    delivery_date: Mapped[str | None] = mapped_column(Date)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class OrderLine(TenantScopedBase):
    """订单明细行：产品名称、规格型号、单位、数量、单价、金额(=数量×单价)。
    支持部分/全部发货——shipped_quantity 记录已发货数量。"""
    __tablename__ = "order_lines"

    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_id: Mapped[str | None] = mapped_column(String(36))
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(200))  # 规格型号
    unit: Mapped[str | None] = mapped_column(String(32))   # 单位
    quantity: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)  # 数量×单价
    shipped_quantity: Mapped[float] = mapped_column(Numeric(18, 3), default=0)  # 已发货数量
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
