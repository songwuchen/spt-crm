# -*- coding: utf-8 -*-
"""可选范围（人员组 / 部门组）— 表单与流程选人/选部门可复用。"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class PickableScope(TenantScopedBase):
    """租户内命名的可选范围。

    kind:
      - person: 人员可选集合
      - department: 部门可选集合

    rules (JSONB) 示例:
      person: {
        "role_codes": ["room_leader"],
        "user_ids": ["..."],
        "dept_ids": ["..."],          # 这些部门(及下级)下的用户也纳入
        "include_children": true
      }
      department: {
        "dept_ids": ["..."],          # 可选部门根；空=不限制
        "include_children": true
      }
    成员 = 各来源并集；若全部为空则不限制（全员/全部门）。
    """

    __tablename__ = "pickable_scopes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_pickable_scopes_tenant_code"),
        Index("ix_pickable_scopes_tenant_kind", "tenant_id", "kind"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="person")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
