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


class NotificationTemplate(TenantScopedBase):
    __tablename__ = "notification_templates"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g. approval_pending, stage_change, payment_overdue
    title_template: Mapped[str] = mapped_column(String(500), nullable=False)
    content_template: Mapped[str | None] = mapped_column(Text)
    # Templates use {{variable}} syntax: {{customer_name}}, {{project_name}}, {{user_name}}, etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationPreference(TenantScopedBase):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # JSON map of type -> enabled, e.g. {"approval_pending": true, "payment_overdue": false}
    preferences_json: Mapped[dict | None] = mapped_column(JSON)
