"""Tests for the RBAC catalog + sync engine (app.common.rbac_catalog / rbac_sync).

Pure catalog-invariant tests need no DB. The sync tests run against the live DB
in a session that is ALWAYS rolled back (the sync service flushes but never
commits), using a throwaway tenant id so nothing real is touched.
"""
import pytest
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
import app.domains.organization.models  # noqa: F401 — register ORM mappers
from app.domains.auth.models import Role, RolePermission, Permission
from app.database import generate_uuid
from app.common import rbac_catalog as cat
from app.common import rbac_sync

TEST_TENANT = "ffffffff-ffff-ffff-ffff-ffffffffffff"


# ----------------------------- pure catalog invariants -----------------------------

def test_permission_codes_unique():
    codes = [p[0] for p in cat.PERMISSIONS]
    assert len(codes) == len(set(codes)), "duplicate permission codes in catalog"


def test_no_dangling_role_permission_refs():
    valid = {p[0] for p in cat.PERMISSIONS}
    for rd in cat.STANDARD_ROLES:
        for code in cat.role_perm_codes(rd):
            assert code in valid, f"role {rd['code']} references undefined perm {code}"


def test_role_perm_codes_are_deduped():
    for rd in cat.STANDARD_ROLES:
        codes = cat.role_perm_codes(rd)
        assert len(codes) == len(set(codes)), f"role {rd['code']} has duplicate perms"


def test_every_role_gets_core_use_tier():
    for rd in cat.STANDARD_ROLES:
        codes = set(cat.role_perm_codes(rd))
        assert set(cat.CORE) <= codes, f"role {rd['code']} missing CORE"


def test_employee_role_is_use_tier_only():
    emp = next(r for r in cat.STANDARD_ROLES if r["code"] == "employee")
    codes = set(cat.role_perm_codes(emp))
    assert {"form:view", "form_data:create", "dashboard:view", "workflow:view"} <= codes
    # baseline employee must NOT get the low-code design tier
    assert not (set(cat.LOWCODE_DESIGN) & codes)


def test_only_lowcode_admin_roles_get_design_tier():
    design = set(cat.LOWCODE_DESIGN)
    for rd in cat.STANDARD_ROLES:
        codes = set(cat.role_perm_codes(rd))
        if rd.get("lowcode_admin"):
            assert design <= codes, f"{rd['code']} should have design tier"
        else:
            assert not (design & codes), f"{rd['code']} should NOT have design tier"


# ----------------------------- DB-backed sync (rolled back) -----------------------------

@pytest.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.rollback()  # discard everything — never persist test rows
        await session.close()
        await engine.dispose()


async def test_preview_then_apply_then_idempotent(db):
    p1 = await rbac_sync.preview(db, TEST_TENANT, mode="additive")
    assert p1["summary"]["roles_to_create"] == len(cat.STANDARD_ROLES)
    assert p1["summary"]["perms_to_add"] > 0

    r1 = await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    assert len(r1["created_roles"]) == len(cat.STANDARD_ROLES)
    assert r1["perms_added"] > 0

    # second preview/apply must be a no-op (idempotent)
    p2 = await rbac_sync.preview(db, TEST_TENANT, mode="additive")
    assert p2["summary"]["roles_to_create"] == 0
    assert p2["summary"]["perms_to_add"] == 0
    r2 = await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    assert r2["created_roles"] == [] and r2["perms_added"] == 0


async def test_additive_never_removes_extra_perm(db):
    await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    role = (await db.execute(select(Role).where(
        Role.tenant_id == TEST_TENANT, Role.code == "employee"))).scalar_one()
    extra = (await db.execute(select(Permission).where(Permission.code == "contract:delete"))).scalar_one()
    db.add(RolePermission(id=generate_uuid(), tenant_id=TEST_TENANT,
                          role_id=role.id, permission_id=extra.id))
    await db.flush()

    # additive preview/apply must NOT flag or remove the extra perm
    p = await rbac_sync.preview(db, TEST_TENANT, mode="additive")
    assert p["summary"]["perms_to_remove"] == 0
    r = await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    assert r["perms_removed"] == 0


async def test_reset_removes_non_catalog_perm(db):
    await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    role = (await db.execute(select(Role).where(
        Role.tenant_id == TEST_TENANT, Role.code == "employee"))).scalar_one()
    extra = (await db.execute(select(Permission).where(Permission.code == "contract:delete"))).scalar_one()
    db.add(RolePermission(id=generate_uuid(), tenant_id=TEST_TENANT,
                          role_id=role.id, permission_id=extra.id))
    await db.flush()

    prev = await rbac_sync.preview(db, TEST_TENANT, mode="reset")
    assert "employee" in prev["perms_to_remove"]
    rep = await rbac_sync.apply(db, TEST_TENANT, mode="reset")
    assert rep["perms_removed"] >= 1
    after = await rbac_sync.preview(db, TEST_TENANT, mode="reset")
    assert "employee" not in after["perms_to_remove"]


async def test_reset_realigns_data_scope(db):
    await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    role = (await db.execute(select(Role).where(
        Role.tenant_id == TEST_TENANT, Role.code == "employee"))).scalar_one()
    role.data_scope = "all"  # drift away from catalog ("self")
    await db.flush()

    prev = await rbac_sync.preview(db, TEST_TENANT, mode="reset")
    codes = [r["code"] for r in prev["roles_to_update"]]
    assert "employee" in codes
    # additive must NOT touch scope
    prev_add = await rbac_sync.preview(db, TEST_TENANT, mode="additive")
    assert prev_add["summary"]["roles_to_update"] == 0

    await rbac_sync.apply(db, TEST_TENANT, mode="reset")
    await db.refresh(role)
    assert role.data_scope == "self"


async def test_sync_all_tenants_additive_tops_up_existing_role(db):
    await rbac_sync.apply(db, TEST_TENANT, mode="additive")
    role = (await db.execute(select(Role).where(
        Role.tenant_id == TEST_TENANT, Role.code == "employee"))).scalar_one()
    fv = (await db.execute(select(Permission).where(Permission.code == "form:view"))).scalar_one()
    await db.execute(sa_delete(RolePermission).where(
        RolePermission.role_id == role.id, RolePermission.permission_id == fv.id))
    await db.flush()

    res = await rbac_sync.sync_all_tenants_additive(db)
    assert res["_total_perms_added"] >= 1
    # employee should have form:view back — additive preview no longer wants to add it
    p = await rbac_sync.preview(db, TEST_TENANT, mode="additive")
    assert "employee" not in p["perms_to_add"]
