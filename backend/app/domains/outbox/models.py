from sqlalchemy import String, Text, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class OutboxEvent(TenantScopedBase):
    """Outbox pattern: events produced by this system, to be published externally."""
    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. project.stage_advanced, contract.signed, payment.received
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g. project, contract, payment
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending / published / failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    published_by: Mapped[str | None] = mapped_column(String(100))
    # worker name or channel


class InboxEvent(TenantScopedBase):
    """Inbox pattern: events received from external systems to be processed."""
    __tablename__ = "inbox_events"

    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. erp, email, webhook
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    # idempotency key
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="received", index=True)
    # received / processing / processed / failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[str | None] = mapped_column(String(30))
