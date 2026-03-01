from sqlalchemy import String, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Solution(TenantScopedBase):
    __tablename__ = "solutions"

    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    solution_no: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/reviewing/approved/obsolete
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class SolutionVersion(TenantScopedBase):
    __tablename__ = "solution_versions"

    solution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[dict | None] = mapped_column(JSON)
    risk_list_json: Mapped[dict | None] = mapped_column(JSON)
    ai_insights_json: Mapped[dict | None] = mapped_column(JSON)
    doc_attachment_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/reviewing/approved
