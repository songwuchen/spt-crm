from sqlalchemy import String, Text, JSON, Integer, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Invoice(TenantScopedBase):
    __tablename__ = "invoices"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    invoice_no: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    invoice_date: Mapped[str | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="issued")  # issued/void
    erp_ref_json: Mapped[dict | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class PaymentPlan(TenantScopedBase):
    __tablename__ = "payment_plans"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_no: Mapped[str] = mapped_column(String(100), nullable=False)
    due_date: Mapped[str | None] = mapped_column(Date)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    trigger_milestone_code: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/paid/overdue
    remark: Mapped[str | None] = mapped_column(Text)
    # 子模块负责人（多部门/多人协作）
    assignee_id: Mapped[str | None] = mapped_column(String(36), index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(100))


class PaymentRecord(TenantScopedBase):
    __tablename__ = "payment_records"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    received_date: Mapped[str | None] = mapped_column(Date)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    channel: Mapped[str | None] = mapped_column(String(64))
    reference_no: Mapped[str | None] = mapped_column(String(100))
    matched_plan_id: Mapped[str | None] = mapped_column(String(36))
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
