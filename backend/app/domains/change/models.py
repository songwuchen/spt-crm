from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ChangeRequest(TenantScopedBase):
    __tablename__ = "change_requests"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    change_no: Mapped[str] = mapped_column(String(64), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # requirement/quote/contract/delivery
    from_version_ref_json: Mapped[dict | None] = mapped_column(JSON)
    to_version_ref_json: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    impact_json: Mapped[dict | None] = mapped_column(JSON)
    # {cost, schedule, scope, risk}
    status: Mapped[str] = mapped_column(String(16), default="draft")
    # draft/reviewing/approved/rejected/implemented
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    # 子模块负责人（多部门/多人协作）
    assignee_id: Mapped[str | None] = mapped_column(String(36), index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(100))
