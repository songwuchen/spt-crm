from datetime import datetime

from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, Index
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


class DeptRoleRule(TenantScopedBase):
    """部门 → 角色 自动分配规则。

    用户被加入(新建/编辑)或从钉钉同步进匹配部门时，自动补上对应角色。
    仅新增、绝不删除已有角色(additive)——不会覆盖管理员手工设置或升级的角色。
    include_children=True 时，子部门成员也命中(按 Department.path 前缀匹配)。
    role_id 直接指向本租户的 Role 行，从模型层杜绝跨租户角色注入。
    """
    __tablename__ = "dept_role_rules"

    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("departments.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)
    include_children: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        # 同一部门+角色只允许一条规则
        Index("uq_dept_role_rule", "tenant_id", "department_id", "role_id", unique=True),
        # 角色维度的清理/查询(如删除角色时按 role_id 清规则)走索引，避免全表扫
        Index("ix_dept_role_rule_role", "tenant_id", "role_id"),
    )


# ===== 组织模型扩展(Phase 3 审批人解析) =====

class Post(TenantScopedBase):
    """岗位。支持审批人类型「指定岗位」(specified_post)。"""
    __tablename__ = "posts"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    __table_args__ = (
        Index("uq_posts_tenant_code", "tenant_id", "code", unique=True),
    )


class UserPost(TenantScopedBase):
    """用户-岗位关系(多对多)。"""
    __tablename__ = "user_posts"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id"), nullable=False)

    __table_args__ = (
        Index("ix_user_posts_user", "user_id"),
        Index("ix_user_posts_post", "post_id"),
    )


class UserAgent(TenantScopedBase):
    """代理审批: 用户在指定时间段内由代理人代为审批。"""
    __tablename__ = "user_agents"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_user_agents_user", "user_id"),
        Index("ix_user_agents_agent", "agent_id"),
    )
