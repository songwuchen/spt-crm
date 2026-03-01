from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class AuditLog(TenantScopedBase):
    __tablename__ = "audit_logs"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create / update / delete / qualify / discard
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # customer / lead / contact / user ...
    resource_id: Mapped[str | None] = mapped_column(String(36))
    summary: Mapped[str | None] = mapped_column(String(500))
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(50))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    trace_id: Mapped[str | None] = mapped_column(String(36))
