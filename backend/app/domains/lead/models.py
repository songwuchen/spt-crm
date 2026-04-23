from sqlalchemy import String, Text, Integer, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Lead(TenantScopedBase):
    __tablename__ = "leads"

    lead_code: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(300))
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    contact_raw_json: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(100))  # expo/referral/ad/inbound/partner/call
    source_detail_json: Mapped[dict | None] = mapped_column(JSON)
    demand_summary: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(100))
    customer_type: Mapped[str | None] = mapped_column(String(50))  # DataDictionary(dict_type=customer_type)
    category: Mapped[str | None] = mapped_column(String(20))  # self_reported / distributed
    country_type: Mapped[str | None] = mapped_column(String(20))  # domestic / overseas
    country_name: Mapped[str | None] = mapped_column(String(100))  # only set when country_type=overseas
    region: Mapped[str | None] = mapped_column(String(200))  # legacy free-text, kept for back-compat
    province: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    district: Mapped[str | None] = mapped_column(String(50))
    department_id: Mapped[str | None] = mapped_column(String(36))
    budget_range: Mapped[str | None] = mapped_column(String(100))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="new")  # new / following / qualified / discarded
    score: Mapped[int] = mapped_column(Integer, default=0)
    converted_customer_id: Mapped[str | None] = mapped_column(String(36))
    remark: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
