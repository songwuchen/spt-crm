from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import TenantScopedBase


class Department(TenantScopedBase):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("departments.id"))
    path: Mapped[str] = mapped_column(String(1000), default="")  # materialized path e.g. "/root/sub1/sub2"
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    leader_id: Mapped[str | None] = mapped_column(String(36))

    children: Mapped[list["Department"]] = relationship(
        back_populates="parent", lazy="selectin"
    )
    parent: Mapped["Department | None"] = relationship(
        back_populates="children", remote_side="Department.id", lazy="selectin"
    )


class UserDepartment(TenantScopedBase):
    __tablename__ = "user_departments"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("departments.id"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="user_departments")
    department: Mapped["Department"] = relationship(lazy="selectin")
