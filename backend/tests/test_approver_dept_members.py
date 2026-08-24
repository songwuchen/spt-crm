# -*- coding: utf-8 -*-
"""审批人/抄送人：部门全体成员解析。"""
from app.database import generate_uuid
from app.domains.auth.models import User
from app.domains.lowcode.approver_resolver import ApprovalContext, ApproverResolver
from app.domains.organization.models import Department, UserDepartment
from tests.lead_intel_helpers import DEMO_TENANT


async def _seed_dept_users(db):
    suffix = generate_uuid()[:8]
    parent = Department(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=f"父部门{suffix}", path=f"/父{suffix}",
    )
    child = Department(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=f"子部门{suffix}", path=f"/父{suffix}/子{suffix}",
        parent_id=parent.id,
    )
    u1 = User(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        username=f"dm_u1_{suffix}", real_name="成员甲",
        password_hash="x", is_active=True,
    )
    u2 = User(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        username=f"dm_u2_{suffix}", real_name="成员乙",
        password_hash="x", is_active=True,
    )
    db.add_all([parent, child, u1, u2])
    await db.flush()
    db.add_all([
        UserDepartment(
            id=generate_uuid(), tenant_id=DEMO_TENANT,
            user_id=u1.id, department_id=parent.id,
        ),
        UserDepartment(
            id=generate_uuid(), tenant_id=DEMO_TENANT,
            user_id=u2.id, department_id=child.id,
        ),
    ])
    await db.commit()
    return parent, child, u1, u2


async def test_dept_members_fixed(db):
    parent, child, u1, u2 = await _seed_dept_users(db)
    resolver = ApproverResolver(db, DEMO_TENANT)
    ids = await resolver.resolve(
        {"type": "dept_members", "value": [parent.id]},
        ApprovalContext(initiator_id=u1.id, form_data={}),
    )
    assert u1.id in ids
    assert u2.id not in ids

    ids_sub = await resolver.resolve(
        {"type": "dept_members", "value": [parent.id], "include_sub": True},
        ApprovalContext(initiator_id=u1.id, form_data={}),
    )
    assert u1.id in ids_sub
    assert u2.id in ids_sub


async def test_form_field_dept_members(db):
    parent, child, u1, u2 = await _seed_dept_users(db)
    resolver = ApproverResolver(db, DEMO_TENANT)
    ids = await resolver.resolve(
        {"type": "form_field_dept_members", "value": "department", "include_sub": True},
        ApprovalContext(initiator_id=u1.id, form_data={"department": parent.id}),
    )
    assert u1.id in ids
    assert u2.id in ids
