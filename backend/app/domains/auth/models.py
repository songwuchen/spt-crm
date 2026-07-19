from sqlalchemy import String, Boolean, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

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
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 账号由系统代建（如钉钉组织同步）、密码是全租户共享的默认值，用户本人从未设过密码。
    # 为 True 时允许「修改密码」免填原密码——本人根本无从知晓那个默认密码。
    # 用户任意一次自助改密后置为 False，此后恢复常规的原密码校验。
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

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
    # 数据范围：None/self=仅本人、dept=本部门及下级、all=全部
    data_scope: Mapped[str | None] = mapped_column(String(16))

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

    # 同一用户同一角色只允许一行——支撑「部门→角色」自动补角色的 ON CONFLICT 幂等，
    # 并防止并发/重复分配产生重复角色行。
    __table_args__ = (
        Index("uq_user_role", "tenant_id", "user_id", "role_id", unique=True),
    )

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates=None, lazy="selectin")


class RolePermission(TenantScopedBase):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[str] = mapped_column(String(36), ForeignKey("permissions.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(lazy="selectin")


class LoginSession(TenantScopedBase):
    __tablename__ = "login_sessions"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(50))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    device_type: Mapped[str | None] = mapped_column(String(30))  # desktop / mobile / tablet
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
