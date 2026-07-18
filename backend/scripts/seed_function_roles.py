"""Idempotent seeding / realignment of the STANDARD FUNCTION roles for ONE tenant.

Role & permission definitions live in the single source of truth
``app.common.rbac_catalog`` (shared with ``scripts/seed.py`` and the admin
「同步标准角色与权限」API). This CLI HARD-SYNCS each standard role's perms to the
catalog (it REMOVES anything not in the catalog) — use it for a full, destructive
realignment of one tenant.

    # 1) dry-run — prints what would change, writes nothing
    docker compose exec -T backend python -m scripts.seed_function_roles
    # 2) apply
    docker compose exec -T backend python -m scripts.seed_function_roles --apply

Creates/updates roles by (tenant_id, code), syncs each role's permissions to
exactly the catalog list, and sets name/description/data_scope. Does NOT touch
users or custom / person-named roles. Re-runnable.

TENANT_ID defaults to the demo/main tenant; override with env TENANT_ID.

NOTE: for day-to-day use prefer the ADDITIVE sync (admin API button, or the
auto cross-tenant sync in scripts/seed.py) — those never strip perms. This CLI
stays for an explicit full realignment.
"""
import asyncio
import os
import sys

from sqlalchemy import select

from app.database import async_session_factory, generate_uuid
from app.domains.auth.models import Role, Permission, RolePermission
import app.domains.organization.models  # noqa: F401 — register ORM mappers (User.user_departments)
from app.common.rbac_catalog import STANDARD_ROLES as ROLE_DEFS, role_perm_codes

TENANT_ID = os.environ.get("TENANT_ID", "00000000-0000-0000-0000-000000000001")
APPLY = "--apply" in sys.argv


async def main():
    async with async_session_factory() as db:
        perms = (await db.execute(select(Permission))).scalars().all()
        pid = {p.code: p.id for p in perms}

        print(f"tenant={TENANT_ID}  mode={'APPLY' if APPLY else 'DRY-RUN (use --apply to write)'}\n")
        for rd in ROLE_DEFS:
            codes = role_perm_codes(rd)  # CORE + role perms + (LOWCODE_DESIGN if lowcode_admin)
            missing = [c for c in codes if c not in pid]
            if missing:
                print(f"  !! {rd['code']}: unknown permission codes -> {missing}")
            want = {pid[c] for c in codes if c in pid}

            role = (await db.execute(
                select(Role).where(Role.tenant_id == TENANT_ID, Role.code == rd["code"])
            )).scalar_one_or_none()
            if role is None:
                action = "CREATE"
                if APPLY:
                    role = Role(
                        id=generate_uuid(), tenant_id=TENANT_ID, code=rd["code"],
                        name=rd["name"], description=rd.get("desc"),
                        data_scope=rd["scope"], is_system=False,
                    )
                    db.add(role)
                    await db.flush()
            else:
                action = "UPDATE"
                if APPLY:
                    role.name = rd["name"]
                    role.description = rd.get("desc")
                    role.data_scope = rd["scope"]

            added = removed = 0
            if APPLY and role is not None:
                existing = (await db.execute(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                )).scalars().all()
                have = {rp.permission_id for rp in existing}
                for rp in existing:
                    if rp.permission_id not in want:
                        await db.delete(rp); removed += 1
                for p_id in (want - have):
                    db.add(RolePermission(
                        id=generate_uuid(), tenant_id=TENANT_ID,
                        role_id=role.id, permission_id=p_id,
                    )); added += 1

            print(f"  {action:6} {rd['code']:20} scope={rd['scope']:4} perms={len(want):2}"
                  + (f"  (+{added}/-{removed})" if APPLY else ""))

        if APPLY:
            await db.commit()
            print("\n✓ committed.")
        else:
            print("\n(dry-run) nothing written. Re-run with --apply to create the roles.")


if __name__ == "__main__":
    asyncio.run(main())
