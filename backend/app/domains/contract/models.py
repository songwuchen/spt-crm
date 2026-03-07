from sqlalchemy import String, Text, JSON, Integer, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Contract(TenantScopedBase):
    __tablename__ = "contracts"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contract_no: Mapped[str] = mapped_column(String(64), nullable=False)
    from_quote_id: Mapped[str | None] = mapped_column(String(36), index=True)
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/signed/terminated
    signed_date: Mapped[str | None] = mapped_column(Date)
    end_date: Mapped[str | None] = mapped_column(Date)
    amount_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    payment_terms_json: Mapped[dict | None] = mapped_column(JSON)
    delivery_terms_json: Mapped[dict | None] = mapped_column(JSON)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class ContractVersion(TenantScopedBase):
    __tablename__ = "contract_versions"

    contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    doc_attachment_id: Mapped[str | None] = mapped_column(String(36))
    key_clauses_json: Mapped[dict | None] = mapped_column(JSON)
    risk_level: Mapped[str | None] = mapped_column(String(2))  # L/M/H
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/approved/signed
