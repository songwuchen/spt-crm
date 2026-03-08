from sqlalchemy import String, Text, JSON, DateTime, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Activity(TenantScopedBase):
    __tablename__ = "activities"

    biz_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # customer / project / lead
    biz_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # call / visit / meeting / email / note / stage_change / system
    subject: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[str | None] = mapped_column(Text)
    contact_id: Mapped[str | None] = mapped_column(String(36), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(100))
    result_json: Mapped[dict | None] = mapped_column(JSON)
    # e.g. {"action_items": [...], "next_step": "..."}
    next_follow_date: Mapped[str | None] = mapped_column(Date)
    biz_name: Mapped[str | None] = mapped_column(String(200))
    mentions_json: Mapped[list | None] = mapped_column(JSON)
    # [{"user_id": "...", "user_name": "..."}]
    pinned: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
