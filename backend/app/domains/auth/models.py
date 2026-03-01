from sqlalchemy import String, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import TenantScopedBase, PlatformBase


class User(TenantScopedBase):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    avatar: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="user", lazy="selectin")
    user_departments: Mapped[list["UserDepartment"]] = relationship(
        "UserDepartment", back_populates="user", lazy="selectin"
    )


class Role(TenantScopedBase):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    role_permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", lazy="selectin")


class Permission(PlatformBase):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)


class UserRole(TenantScopedBase):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates=None, lazy="selectin")


class RolePermission(TenantScopedBase):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[str] = mapped_column(String(36), ForeignKey("permissions.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(lazy="selectin")
