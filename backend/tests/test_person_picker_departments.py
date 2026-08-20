from app.domains.organization.pickable_scope_service import department_names_by_user_ids


async def test_department_names_by_user_ids(db):
    from app.database import generate_uuid
    from app.domains.auth.models import User
    from app.domains.organization.models import Department, UserDepartment
    from tests.lead_intel_helpers import DEMO_TENANT

    tenant = DEMO_TENANT
    suffix = generate_uuid()[:8]
    dept_a = Department(
        id=generate_uuid(), tenant_id=tenant, name=f"销售一部{suffix}", path=f"/销售一部{suffix}",
    )
    dept_b = Department(
        id=generate_uuid(), tenant_id=tenant, name=f"华北区{suffix}", path=f"/华北区{suffix}",
    )
    u1 = User(
        id=generate_uuid(), tenant_id=tenant, username=f"u_dept_a_{suffix}",
        real_name="张三", password_hash="x", is_active=True,
    )
    u2 = User(
        id=generate_uuid(), tenant_id=tenant, username=f"u_no_dept_{suffix}",
        real_name="李四", password_hash="x", is_active=True,
    )
    db.add_all([dept_a, dept_b, u1, u2])
    await db.flush()
    db.add_all([
        UserDepartment(
            id=generate_uuid(), tenant_id=tenant, user_id=u1.id, department_id=dept_a.id,
        ),
        UserDepartment(
            id=generate_uuid(), tenant_id=tenant, user_id=u1.id, department_id=dept_b.id,
        ),
    ])
    await db.commit()

    out = await department_names_by_user_ids(db, tenant, [u1.id, u2.id, "missing"])
    assert out[u1.id] == [f"华北区{suffix}", f"销售一部{suffix}"]
    assert out.get(u2.id) is None
