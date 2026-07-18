"""Idempotent RBAC sync — bring a tenant's STANDARD roles in line with the
canonical catalog (:mod:`app.common.rbac_catalog`).

Used by:
  - the admin「同步标准角色与权限」API (per tenant: preview + apply)
  - ``scripts/seed.py`` on deploy (additive, across every tenant that already
    has standard roles — so new-feature perms auto-reach all environments)

Modes:
  - ``additive`` (default): create missing standard roles (when
    ``create_missing_roles``), ADD missing standard perms to standard roles.
    Never removes anything, never modifies an existing role's name/scope, never
    touches custom / person-named roles.
  - ``reset``: full realignment — also REMOVE non-catalog perms from standard
    roles AND realign their name/description/data_scope to the catalog.

Service functions do NOT commit — the caller owns the transaction.
"""
from sqlalchemy import select, delete as sa_delete

from app.database import generate_uuid
from app.domains.auth.models import Role, Permission, RolePermission
from app.common.rbac_catalog import (
    PERMISSIONS, STANDARD_ROLES, STANDARD_ROLE_CODES, role_perm_codes,
)

_ROLE_BY_CODE = {r["code"]: r for r in STANDARD_ROLES}
_ALL_CATALOG_CODES = frozenset(c for c, _, _ in PERMISSIONS)


async def _ensure_permissions(db, *, write: bool) -> dict:
    """Return ``{code: Permission}``. When ``write``, insert any missing catalog
    permission rows and fix display name/group drift (flush, no commit)."""
    existing = {p.code: p for p in (await db.execute(select(Permission))).scalars().all()}
    if write:
        changed = False
        for code, name, group in PERMISSIONS:
            p = existing.get(code)
            if p is None:
                p = Permission(id=generate_uuid(), code=code, name=name, group_name=group)
                db.add(p)
                existing[code] = p
                changed = True
            elif p.name != name or p.group_name != group:
                p.name, p.group_name = name, group
                changed = True
        if changed:
            await db.flush()
    return existing


async def _plan(db, tenant_id, perms_by_code, *, mode, create_missing_roles, valid_codes=None):
    """Compute the sync plan for one tenant in code-space (no writes).

    ``valid_codes`` = permission codes considered assignable (defaults to the
    codes present in ``perms_by_code``). Preview passes existing ∪ catalog codes
    so a not-yet-created catalog perm still shows up in ``adds`` (apply creates
    then assigns it — keeping preview and apply in agreement).

    Returns ``(existing_roles, creates, adds, removes, meta_updates)``:
      - ``creates``       list of ``{code,name,scope,perms}``
      - ``adds``/``removes`` ``{role_code: [perm_code, ...]}`` (existing roles)
      - ``meta_updates``  ``{role_code: [changed_field_label, ...]}`` (reset only)
    """
    if valid_codes is None:
        valid_codes = set(perms_by_code)

    roles = {r.code: r for r in (await db.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.code.in_(STANDARD_ROLE_CODES))
    )).scalars().all()}

    now = {code: set() for code in roles}
    if roles:
        id_to_code = {p.id: c for c, p in perms_by_code.items()}
        role_by_id = {r.id: r.code for r in roles.values()}
        rows = (await db.execute(select(RolePermission).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id.in_([r.id for r in roles.values()]),
        ))).scalars().all()
        for rp in rows:
            rc = role_by_id.get(rp.role_id)
            code = id_to_code.get(rp.permission_id)
            if rc and code:
                now[rc].add(code)

    creates, adds, removes, meta_updates = [], {}, {}, {}
    for rd in STANDARD_ROLES:
        want = [c for c in role_perm_codes(rd) if c in valid_codes]
        want_set = set(want)
        role = roles.get(rd["code"])
        if role is None:
            if create_missing_roles:
                creates.append({"code": rd["code"], "name": rd["name"],
                                "scope": rd["scope"], "perms": want})
            continue
        cur = now[rd["code"]]
        add = [c for c in want if c not in cur]
        if add:
            adds[rd["code"]] = add
        if mode == "reset":
            rem = sorted(cur - want_set)
            if rem:
                removes[rd["code"]] = rem
            changed = []
            if role.name != rd["name"]:
                changed.append("名称")
            if (role.description or None) != (rd.get("desc") or None):
                changed.append("描述")
            if (role.data_scope or "self") != rd["scope"]:
                changed.append("数据范围")
            if changed:
                meta_updates[rd["code"]] = changed
    return roles, creates, adds, removes, meta_updates


async def preview(db, tenant_id, *, mode="additive", create_missing_roles=True) -> dict:
    """Read-only diff of what a sync would change for ``tenant_id``."""
    perms_by_code = await _ensure_permissions(db, write=False)
    # Include catalog codes not yet in the DB so preview matches what apply grants.
    valid_codes = set(perms_by_code) | _ALL_CATALOG_CODES
    _, creates, adds, removes, meta_updates = await _plan(
        db, tenant_id, perms_by_code, mode=mode,
        create_missing_roles=create_missing_roles, valid_codes=valid_codes)
    perm_names = {p[0]: p[1] for p in PERMISSIONS}
    missing_perm_rows = [c for c in _ALL_CATALOG_CODES if c not in perms_by_code]
    return {
        "mode": mode,
        "roles_to_create": [
            {"code": c["code"], "name": _ROLE_BY_CODE[c["code"]]["name"], "perm_count": len(c["perms"])}
            for c in creates
        ],
        "perms_to_add": {rc: [{"code": c, "name": perm_names.get(c, c)} for c in codes]
                         for rc, codes in adds.items()},
        "perms_to_remove": {rc: [{"code": c, "name": perm_names.get(c, c)} for c in codes]
                            for rc, codes in removes.items()},
        "roles_to_update": [{"code": c, "changes": ch} for c, ch in meta_updates.items()],
        "permissions_to_create": missing_perm_rows,
        "summary": {
            "roles_to_create": len(creates),
            "perms_to_add": sum(len(v) for v in adds.values()) + sum(len(c["perms"]) for c in creates),
            "perms_to_remove": sum(len(v) for v in removes.values()),
            "roles_to_update": len(meta_updates),
            "permissions_to_create": len(missing_perm_rows),
        },
    }


async def apply(db, tenant_id, *, mode="additive", create_missing_roles=True) -> dict:
    """Apply the sync for ``tenant_id`` (flush only — caller commits)."""
    perms_by_code = await _ensure_permissions(db, write=True)
    roles, creates, adds, removes, meta_updates = await _plan(
        db, tenant_id, perms_by_code, mode=mode, create_missing_roles=create_missing_roles)

    for c in creates:
        rd = _ROLE_BY_CODE[c["code"]]
        role = Role(id=generate_uuid(), tenant_id=tenant_id, code=rd["code"], name=rd["name"],
                    description=rd.get("desc"), data_scope=rd["scope"], is_system=False)
        db.add(role)
        await db.flush()
        roles[rd["code"]] = role
        for code in c["perms"]:
            db.add(RolePermission(id=generate_uuid(), tenant_id=tenant_id,
                                  role_id=role.id, permission_id=perms_by_code[code].id))

    for rcode, codes in adds.items():
        role = roles[rcode]
        for code in codes:
            db.add(RolePermission(id=generate_uuid(), tenant_id=tenant_id,
                                  role_id=role.id, permission_id=perms_by_code[code].id))

    if mode == "reset":
        for rcode, codes in removes.items():
            ids = [perms_by_code[c].id for c in codes if c in perms_by_code]
            if ids:
                await db.execute(sa_delete(RolePermission).where(
                    RolePermission.tenant_id == tenant_id,
                    RolePermission.role_id == roles[rcode].id,
                    RolePermission.permission_id.in_(ids),
                ))
        # Realign role name/description/data_scope to the catalog.
        for rcode in meta_updates:
            role, rd = roles[rcode], _ROLE_BY_CODE[rcode]
            role.name = rd["name"]
            role.description = rd.get("desc")
            role.data_scope = rd["scope"]

    await db.flush()
    return {
        "mode": mode,
        "created_roles": [c["code"] for c in creates],
        "perms_added": sum(len(v) for v in adds.values()) + sum(len(c["perms"]) for c in creates),
        "perms_removed": sum(len(v) for v in removes.values()),
        "roles_updated": list(meta_updates.keys()),
        "roles_touched": sorted(set(c["code"] for c in creates) | set(adds) | set(removes) | set(meta_updates)),
    }


async def sync_all_tenants_additive(db, perms_by_code=None) -> dict:
    """Deploy hook: additively sync standard roles for EVERY tenant that already
    has at least one standard role. Never creates roles in tenants that lack them,
    never removes. Flush only — caller commits. Returns a per-tenant add count.

    ``perms_by_code`` may be supplied by a caller that already loaded/created the
    permission rows (e.g. scripts/seed.py) to avoid re-scanning the table."""
    if perms_by_code is None:
        perms_by_code = await _ensure_permissions(db, write=True)
    valid = set(perms_by_code)
    tenant_ids = [row[0] for row in (await db.execute(
        select(Role.tenant_id).where(Role.code.in_(STANDARD_ROLE_CODES)).distinct()
    )).all()]

    result, total = {}, 0
    for tid in tenant_ids:
        roles, _, adds, _, _ = await _plan(
            db, tid, perms_by_code, mode="additive", create_missing_roles=False, valid_codes=valid)
        n = 0
        for rcode, codes in adds.items():
            role = roles.get(rcode)
            if role is None:
                continue
            for code in codes:
                db.add(RolePermission(id=generate_uuid(), tenant_id=tid,
                                      role_id=role.id, permission_id=perms_by_code[code].id))
                n += 1
        if n:
            result[tid] = n
            total += n
    await db.flush()
    result["_total_perms_added"] = total
    result["_tenants_scanned"] = len(tenant_ids)
    return result
