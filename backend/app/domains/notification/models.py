from sqlalchemy import String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Notification(TenantScopedBase):
    __tablename__ = "notifications"

    recipient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # types: approval_pending, approval_decided, stage_change, payment_overdue,
    #        ai_task_complete, gate_blocked, system
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    biz_type: Mapped[str | None] = mapped_column(String(64))
    biz_id: Mapped[str | None] = mapped_column(String(36))
    sender_name: Mapped[str | None] = mapped_column(String(100))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_json: Mapped[dict | None] = mapped_column(JSON)
