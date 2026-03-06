from sqlalchemy import String, Text, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class UserTask(TenantScopedBase):
    __tablename__ = "user_tasks"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[str | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(16), default="normal")  # low/normal/high/urgent
    status: Mapped[str] = mapped_column(String(16), default="todo")  # todo/in_progress/done
    assignee_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(100))
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    biz_type: Mapped[str | None] = mapped_column(String(64))  # customer/project/lead/ticket
    biz_id: Mapped[str | None] = mapped_column(String(36))
    biz_name: Mapped[str | None] = mapped_column(String(200))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
