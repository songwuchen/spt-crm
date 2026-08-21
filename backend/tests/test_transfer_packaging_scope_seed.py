"""转新乡、工艺包装可选范围种子成员。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database import generate_uuid
from app.domains.auth.models import User
from app.domains.organization.pickable_scope_models import PickableScope
from app.domains.organization.pickable_scope_service import (
    TRANSFER_PACKAGING_MEMBER_NAMES,
    _user_ids_by_real_names,
    seed_transfer_packaging_users,
)
from tests.lead_intel_helpers import DEMO_TENANT


def test_transfer_packaging_canonical_names():
    assert TRANSFER_PACKAGING_MEMBER_NAMES == (
        "杨光", "赵连华", "李海春", "王昌轲",
    )


@pytest.mark.asyncio
async def test_seed_transfer_packaging_users(db):
    tenant_id = DEMO_TENANT
    for i, name in enumerate(TRANSFER_PACKAGING_MEMBER_NAMES):
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
    scope = (
        await db.execute(
            select(PickableScope).where(
                PickableScope.tenant_id == tenant_id,
                PickableScope.code == "fa-zxxgy",
            )
        )
    ).scalar_one_or_none()
    if not scope:
        scope = PickableScope(
            id=generate_uuid(),
            tenant_id=tenant_id,
            code="fa-zxxgy",
            name="方案管理-转新乡、工艺包装",
            kind="person",
            is_system=True,
            rules={"role_codes": [], "user_ids": [], "dept_ids": [], "include_children": True},
        )
        db.add(scope)
    await db.commit()

    ids, missing = await _user_ids_by_real_names(db, tenant_id, TRANSFER_PACKAGING_MEMBER_NAMES)
    assert len(ids) == 4
    assert missing == []

    changed = await seed_transfer_packaging_users(db, tenant_id)
    assert changed is True
    await db.commit()
    await db.refresh(scope)
    assert len(scope.rules["user_ids"]) == 4

    assert await seed_transfer_packaging_users(db, tenant_id) is False
