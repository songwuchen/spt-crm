"""转新乡、工艺包装：RBAC 角色成员（不再维护 fa-zxxgy 可选范围）。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database import generate_uuid
from app.domains.auth.models import Role, User, UserRole
from app.common.rbac_sync import (
    TRANSFER_PACKAGING_MEMBER_REAL_NAMES,
    ensure_transfer_packaging_role_members,
)
from tests.lead_intel_helpers import DEMO_TENANT


def test_transfer_packaging_canonical_names():
    assert TRANSFER_PACKAGING_MEMBER_REAL_NAMES == (
        "杨光", "赵连华", "李海春", "王昌轲",
    )


@pytest.mark.asyncio
async def test_ensure_transfer_packaging_role_members(db):
    tenant_id = DEMO_TENANT
    for i, name in enumerate(TRANSFER_PACKAGING_MEMBER_REAL_NAMES):
        exists = (
            await db.execute(
                select(User.id).where(
                    User.tenant_id == tenant_id,
                    User.real_name == name,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(User(
            id=generate_uuid(),
            tenant_id=tenant_id,
            username=f"tp_seed_{i}",
            password_hash="x",
            real_name=name,
            is_active=True,
        ))
    await db.commit()

    info = await ensure_transfer_packaging_role_members(db, tenant_id)
    await db.commit()

    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "transfer_packaging")
        )
    ).scalar_one()
    member_count = (
        await db.execute(
            select(UserRole.id).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == role.id,
            )
        )
    ).scalars().all()
    assert len(member_count) == 4
    assert info["added"] >= 0

    info2 = await ensure_transfer_packaging_role_members(db, tenant_id)
    assert info2["added"] == 0
