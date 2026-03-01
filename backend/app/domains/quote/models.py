from sqlalchemy import String, Text, JSON, Integer, Numeric, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Quote(TenantScopedBase):
    __tablename__ = "quotes"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    quote_no: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/sent/won/lost
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class QuoteVersion(TenantScopedBase):
    __tablename__ = "quote_versions"

    quote_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    price_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    tax_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    tax_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    discount_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    margin_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    delivery_promise_date: Mapped[str | None] = mapped_column(Date)
    validity_days: Mapped[int | None] = mapped_column(Integer)
    terms_summary_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/approved/sent


class QuoteLine(TenantScopedBase):
    __tablename__ = "quote_lines"

    quote_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str | None] = mapped_column(String(16))  # standard/nonstandard/service/spare
    item_name: Mapped[str | None] = mapped_column(String(200))
    item_code: Mapped[str | None] = mapped_column(String(100))
    spec: Mapped[str | None] = mapped_column(String(300))
    qty: Mapped[float | None] = mapped_column(Numeric(18, 4))
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    line_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cost_est: Mapped[float | None] = mapped_column(Numeric(18, 2))
    leadtime_days: Mapped[int | None] = mapped_column(Integer)


class CostSnapshot(TenantScopedBase):
    __tablename__ = "cost_snapshots"

    quote_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(String(32), default="manual")  # manual/auto/approval
    price_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cost_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    margin_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    breakdown_json: Mapped[dict | None] = mapped_column(JSON)  # 材料/加工/外协/安装/运输/管理费/风险费
    line_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class QuoteSendLog(TenantScopedBase):
    __tablename__ = "quote_send_logs"

    quote_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    quote_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # email/wechat/print/other
    to_list_json: Mapped[dict | None] = mapped_column(JSON)  # [{name, contact}]
    subject: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    attachments_json: Mapped[dict | None] = mapped_column(JSON)  # [{filename, attachment_id}]
    status: Mapped[str] = mapped_column(String(16), default="sent")  # sent/failed/recalled
    sent_by_id: Mapped[str | None] = mapped_column(String(36))
    sent_by_name: Mapped[str | None] = mapped_column(String(100))
