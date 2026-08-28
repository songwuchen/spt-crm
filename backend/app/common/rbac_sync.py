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
        role = Role(
            id=generate_uuid(), tenant_id=tenant_id, code=rd["code"], name=rd["name"],
            description=rd.get("desc"), data_scope=rd["scope"], is_system=False,
            scope_by_resource=dict(rd.get("scope_by_resource") or {}),
        )
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
        # Realign role name/description/data_scope/scope_by_resource to the catalog.
        for rcode in meta_updates:
            role, rd = roles[rcode], _ROLE_BY_CODE[rcode]
            role.name = rd["name"]
            role.description = rd.get("desc")
            role.data_scope = rd["scope"]
            role.scope_by_resource = dict(rd.get("scope_by_resource") or {})
    else:
        # additive：目录声明的模块范围只补缺失键，不覆盖租户已手工改过的明细
        for rcode, role in roles.items():
            rd = _ROLE_BY_CODE.get(rcode)
            want = (rd or {}).get("scope_by_resource") or {}
            if not want:
                continue
            cur = dict(role.scope_by_resource or {})
            changed = False
            for k, v in want.items():
                if k not in cur:
                    cur[k] = v
                    changed = True
            if changed:
                role.scope_by_resource = cur

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


# 业务流程依赖、需在租户内保证存在的角色（不做全量标准同步）
BUSINESS_ROLE_CODES = (
    "room_leader",
    "transfer_packaging",
    "mkt_support",
    "cs_office",
    "cs_arrange",
    "cs_delay_approve",
    "cs_named_fjj_zdd_jw",
    "cs_service_cc",
    "cs_replace_trace",
    "cs_special_release",
    "cs_service_record",
    "trip_overtime_init15",
    "loan_eng_mgmt",
    "biz_backoffice",
    "jdy_sub_admin",
    "logistics_approval",
    "ship_sales_outbound",
    "gate_guard",
    "prod_material_code",
    "prod_elec_workshop",
    "prod_quality_control",
    "plan_procurement_dept",
    "plan_dispatch_dept",
    "legal",
)


async def ensure_business_roles(
    db, tenant_id: str, codes: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """确保业务依赖角色存在；缺失则按目录创建并挂权限。返回新建的 code 列表。

    flush only — 调用方负责 commit。
    """
    want = [c for c in (codes or BUSINESS_ROLE_CODES) if c in _ROLE_BY_CODE]
    if not want:
        return []
    perms_by_code = await _ensure_permissions(db, write=True)
    existing = {
        r.code: r
        for r in (
            await db.execute(
                select(Role).where(Role.tenant_id == tenant_id, Role.code.in_(want))
            )
        ).scalars().all()
    }
    created: list[str] = []
    for code in want:
        rd = _ROLE_BY_CODE[code]
        if code in existing:
            role = existing[code]
            # 目录改名时同步展示名（如 legal：合同法务 → 法务办理）
            if rd.get("name") and role.name != rd["name"]:
                role.name = rd["name"]
            if rd.get("desc") is not None and role.description != rd.get("desc"):
                role.description = rd.get("desc")
            want_sbr = dict(rd.get("scope_by_resource") or {})
            changed_sbr = False
            if want_sbr:
                cur = dict(role.scope_by_resource or {})
                for k, v in want_sbr.items():
                    # 目录有明确覆盖时写入/校正（如业务员方案三表 self）
                    if cur.get(k) != v:
                        cur[k] = v
                        changed_sbr = True
                if changed_sbr:
                    role.scope_by_resource = cur
            # 补齐目录权限（含 CORE），避免新建后缺 form_data:view 等
            changed_perms = False
            have_pids = {
                rp.permission_id
                for rp in (
                    await db.execute(
                        select(RolePermission).where(
                            RolePermission.tenant_id == tenant_id,
                            RolePermission.role_id == role.id,
                        )
                    )
                ).scalars().all()
            }
            for pcode in role_perm_codes(rd):
                perm = perms_by_code.get(pcode)
                if not perm or perm.id in have_pids:
                    continue
                db.add(RolePermission(
                    id=generate_uuid(),
                    tenant_id=tenant_id,
                    role_id=role.id,
                    permission_id=perm.id,
                ))
                have_pids.add(perm.id)
                changed_perms = True
            if changed_perms or changed_sbr:
                from app.domains.auth.service import invalidate_tenant_auth_cache
                await invalidate_tenant_auth_cache(tenant_id)
            continue
        role = Role(
            id=generate_uuid(),
            tenant_id=tenant_id,
            code=rd["code"],
            name=rd["name"],
            description=rd.get("desc"),
            data_scope=rd["scope"],
            scope_by_resource=dict(rd.get("scope_by_resource") or {}),
            is_system=False,
        )
        db.add(role)
        await db.flush()
        for pcode in role_perm_codes(rd):
            perm = perms_by_code.get(pcode)
            if not perm:
                continue
            db.add(RolePermission(
                id=generate_uuid(),
                tenant_id=tenant_id,
                role_id=role.id,
                permission_id=perm.id,
            ))
        existing[code] = role
        created.append(code)
    if created:
        await db.flush()
    return created


async def _ensure_role_members(
    db,
    tenant_id: str,
    role_code: str,
    usernames: tuple[str, ...] | list[str],
    real_names: tuple[str, ...] | list[str] | None = None,
    *,
    prefer_real_name: str | None = None,
) -> dict:
    """通用：确保角色存在并按 username / real_name 挂成员。flush only。"""
    from app.domains.auth.models import User, UserRole

    created_roles = await ensure_business_roles(db, tenant_id, [role_code])
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == role_code)
        )
    ).scalar_one_or_none()
    if not role:
        return {
            "role_created": False,
            "added": 0,
            "missing_usernames": list(usernames),
        }

    users = (
        await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.username.in_(list(usernames)),
            )
        )
    ).scalars().all() if usernames else []
    by_name = {u.username: u for u in users}
    missing = [u for u in usernames if u not in by_name]

    if prefer_real_name and missing:
        by_real_one = (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.real_name == prefer_real_name,
                    User.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        for u in by_real_one:
            if u.id not in {x.id for x in users}:
                users.append(u)

    have_ids = {u.id for u in users}
    if real_names:
        by_real = (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.real_name.in_(list(real_names)),
                    User.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        for u in by_real:
            if u.id not in have_ids:
                users.append(u)
                have_ids.add(u.id)

    existing_uids: set[str] = set()
    if users:
        existing_uids = set(
            (
                await db.execute(
                    select(UserRole.user_id).where(
                        UserRole.tenant_id == tenant_id,
                        UserRole.role_id == role.id,
                        UserRole.user_id.in_([u.id for u in users]),
                    )
                )
            ).scalars().all()
        )

    added = 0
    touched_uids: list[str] = []
    for u in users:
        if u.id in existing_uids:
            continue
        db.add(UserRole(
            id=generate_uuid(),
            tenant_id=tenant_id,
            user_id=u.id,
            role_id=role.id,
        ))
        added += 1
        touched_uids.append(u.id)
    if added:
        await db.flush()
        from app.domains.auth.service import invalidate_user_auth_cache
        for uid in touched_uids:
            await invalidate_user_auth_cache(uid, tenant_id)
    # 角色新建/补权限时整租户清缓存，避免旧 JWT 前 /me 仍读到旧权限
    if created_roles:
        from app.domains.auth.service import invalidate_tenant_auth_cache
        await invalidate_tenant_auth_cache(tenant_id)
    return {
        "role_created": bool(created_roles),
        "added": added,
        "missing_usernames": missing,
        "member_usernames": [u.username for u in users],
        "member_names": [u.real_name or u.username for u in users],
    }


# 简道云「设计指派27.3~4/1.2.8/6.8/27.16/19.3」(63815e3a7fb607000acc9195)
ROOM_LEADER_MEMBER_USERNAMES: tuple[str, ...] = (
    "02364335378133",  # 曹修国
    "0236562418583",  # 樊磊
    "02365310124408",  # 丰芊
    "01142154504565",  # 刘松潮
    "02365312411349",  # 李兴玉
    "0237444753532",  # 吕芹
    "02365310056917",  # 王东明
    "02365625057413",  # 周彦立
    "061353401635555517",  # 赵小康
)
ROOM_LEADER_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "曹修国", "樊磊", "丰芊", "刘松潮", "李兴玉", "吕芹", "王东明", "周彦立", "赵小康",
)


async def ensure_room_leader_role_members(db, tenant_id: str) -> dict:
    """确保 room_leader=设计指派…，成员仅为简道云名单 9 人；并同步可选范围 room_leaders。"""
    from app.domains.auth.models import User, UserRole
    from app.domains.organization import pickable_scope_service as pss

    result = await _ensure_role_members(
        db,
        tenant_id,
        "room_leader",
        ROOM_LEADER_MEMBER_USERNAMES,
        ROOM_LEADER_MEMBER_REAL_NAMES,
    )
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "room_leader")
        )
    ).scalar_one_or_none()
    if not role:
        return result

    keep_users = (
        await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.username.in_(list(ROOM_LEADER_MEMBER_USERNAMES)),
            )
        )
    ).scalars().all()
    keep_ids = {u.id for u in keep_users}
    by_real = (
        await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.real_name.in_(list(ROOM_LEADER_MEMBER_REAL_NAMES)),
                User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    for u in by_real:
        keep_ids.add(u.id)

    if keep_ids:
        pruned = await db.execute(
            sa_delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == role.id,
                UserRole.user_id.notin_(list(keep_ids)),
            )
        )
        result["pruned"] = int(pruned.rowcount or 0)
    else:
        result["pruned"] = 0
    result["role_name"] = role.name

    # 方案管理「设计指派」字段走可选范围 room_leaders：与角色成员对齐
    await pss.ensure_preset_scopes(db, tenant_id)
    scope = await pss.get_scope_by_code(db, tenant_id, "room_leaders")
    if scope and keep_ids:
        scope.rules = {
            "role_codes": [],
            "user_ids": sorted(keep_ids),
            "dept_ids": [],
            "include_children": True,
        }
        scope.name = "方案管理-设计指派"
        scope.description = (
            "对齐角色「设计指派27.3~4/1.2.8/6.8/27.16/19.3」；"
            "成员：曹修国、樊磊、丰芊、刘松潮、李兴玉、吕芹、王东明、周彦立、赵小康。"
        )
        result["pickable_scope_synced"] = True
        result["pickable_scope_user_count"] = len(keep_ids)
        await db.flush()
    return result


# 简道云「客服内勤」成员
CS_OFFICE_MEMBER_USERNAMES: tuple[str, ...] = (
    "0236446249514",  # 李红敏
    "181359282120075679",  # 付加婧
    "113236314224043072",  # 张丹丹
    "01364955133227249077",  # 段尉利
)
CS_OFFICE_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "李红敏", "付加婧", "张丹丹", "段尉利",
)

# 简道云「转新乡、工艺包装」(6942502ab4606b6b5375dc4f)
TRANSFER_PACKAGING_MEMBER_USERNAMES: tuple[str, ...] = (
    "0615176412841441",  # 杨光
    "092068030535963749",  # 赵连华
    "02482852165926309468",  # 李海春
)
TRANSFER_PACKAGING_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "杨光", "赵连华", "李海春", "王昌轲",
)


async def ensure_transfer_packaging_role_members(db, tenant_id: str) -> dict:
    """确保 transfer_packaging 角色存在，并挂简道云「转新乡、工艺包装」成员。"""
    return await _ensure_role_members(
        db,
        tenant_id,
        "transfer_packaging",
        TRANSFER_PACKAGING_MEMBER_USERNAMES,
        TRANSFER_PACKAGING_MEMBER_REAL_NAMES,
        prefer_real_name="杨光",
    )


async def ensure_cs_office_role_members(db, tenant_id: str) -> dict:
    """确保 cs_office 角色存在，并把简道云客服内勤成员挂上。"""
    return await _ensure_role_members(
        db,
        tenant_id,
        "cs_office",
        CS_OFFICE_MEMBER_USERNAMES,
        CS_OFFICE_MEMBER_REAL_NAMES,
        prefer_real_name="李红敏",
    )


# 简道云「服务申请及反馈-客服安排」：线上仅付加婧（勿再扩成客服抽样名单）
CS_ARRANGE_MEMBER_USERNAMES: tuple[str, ...] = (
    "181359282120075679",  # 付加婧
)
CS_ARRANGE_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "付加婧",
)


async def ensure_cs_arrange_role_members(db, tenant_id: str) -> dict:
    """确保 cs_arrange 成员仅为付加婧（对齐 205 线上配置）。"""
    from app.domains.auth.models import User, UserRole

    result = await _ensure_role_members(
        db,
        tenant_id,
        "cs_arrange",
        CS_ARRANGE_MEMBER_USERNAMES,
        CS_ARRANGE_MEMBER_REAL_NAMES,
        prefer_real_name="付加婧",
    )
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "cs_arrange")
        )
    ).scalar_one_or_none()
    if not role:
        return result

    keep_users = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.username.in_(list(CS_ARRANGE_MEMBER_USERNAMES)),
            )
        )
    ).scalars().all()
    keep_ids = set(keep_users)
    by_real = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.real_name.in_(list(CS_ARRANGE_MEMBER_REAL_NAMES)),
                User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    keep_ids.update(by_real)

    if keep_ids:
        pruned = await db.execute(
            sa_delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == role.id,
                UserRole.user_id.notin_(list(keep_ids)),
            )
        )
        result["pruned"] = int(pruned.rowcount or 0)
    else:
        result["pruned"] = 0
    result["role_name"] = role.name
    return result


# 延期「客服审批」：与客服内勤同班底（简道云未单独导出成员时按内勤挂载）
CS_DELAY_APPROVE_MEMBER_USERNAMES = CS_OFFICE_MEMBER_USERNAMES
CS_DELAY_APPROVE_MEMBER_REAL_NAMES = CS_OFFICE_MEMBER_REAL_NAMES


async def ensure_cs_delay_approve_role_members(db, tenant_id: str) -> dict:
    return await _ensure_role_members(
        db,
        tenant_id,
        "cs_delay_approve",
        CS_DELAY_APPROVE_MEMBER_USERNAMES,
        CS_DELAY_APPROVE_MEMBER_REAL_NAMES,
        prefer_real_name="李红敏",
    )


# 发货通知「物流审批」：孔令山、李娜、马瑞草、韩文祯、张冠杰（或签）
LOGISTICS_APPROVAL_MEMBER_USERNAMES: tuple[str, ...] = (
    "0236433705597",         # 孔令山
    "02362440128774",        # 李娜
    "575448583538947351",    # 马瑞草
    "196558292138209137",    # 韩文祯
    "221707676324076528",    # 张冠杰
)
LOGISTICS_APPROVAL_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "孔令山", "李娜", "马瑞草", "韩文祯", "张冠杰",
)


async def ensure_logistics_approval_role_members(db, tenant_id: str) -> dict:
    return await _ensure_role_members(
        db,
        tenant_id,
        "logistics_approval",
        LOGISTICS_APPROVAL_MEMBER_USERNAMES,
        LOGISTICS_APPROVAL_MEMBER_REAL_NAMES,
    )


# 发货通知「销售出库」：仓库/仓库判定（历史办理人抽样）
SHIP_SALES_OUTBOUND_MEMBER_USERNAMES: tuple[str, ...] = (
    "02366368263850",  # 司丹丹
    "01346931076927160185",  # 段亚非
    "0654354430671114",  # 侯静
)
SHIP_SALES_OUTBOUND_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "司丹丹", "段亚非", "侯静",
)


async def ensure_ship_sales_outbound_role_members(db, tenant_id: str) -> dict:
    return await _ensure_role_members(
        db,
        tenant_id,
        "ship_sales_outbound",
        SHIP_SALES_OUTBOUND_MEMBER_USERNAMES,
        SHIP_SALES_OUTBOUND_MEMBER_REAL_NAMES,
    )


# 门岗保卫组：按姓名模糊匹配本地账号
GATE_GUARD_MEMBER_USERNAMES: tuple[str, ...] = ()
GATE_GUARD_MEMBER_REAL_NAMES: tuple[str, ...] = (
    "门岗", "保卫", "安保",
)


async def ensure_gate_guard_role_members(db, tenant_id: str) -> dict:
    """门岗：优先按姓名模糊匹配本地账号。"""
    from app.domains.auth.models import User, UserRole
    from sqlalchemy import or_

    created_roles = await ensure_business_roles(db, tenant_id, ["gate_guard"])
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "gate_guard")
        )
    ).scalar_one_or_none()
    if not role:
        return {"role_created": False, "added": 0, "missing_usernames": []}

    users = (
        await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.is_active == True,  # noqa: E712
                or_(
                    User.real_name.contains("门岗"),
                    User.real_name.contains("保卫"),
                    User.real_name.contains("安保"),
                ),
            )
        )
    ).scalars().all()

    existing_uids: set[str] = set()
    if users:
        existing_uids = set(
            (
                await db.execute(
                    select(UserRole.user_id).where(
                        UserRole.tenant_id == tenant_id,
                        UserRole.role_id == role.id,
                        UserRole.user_id.in_([u.id for u in users]),
                    )
                )
            ).scalars().all()
        )
    added = 0
    for u in users:
        if u.id in existing_uids:
            continue
        db.add(UserRole(
            id=generate_uuid(),
            tenant_id=tenant_id,
            user_id=u.id,
            role_id=role.id,
        ))
        added += 1
    if added:
        await db.flush()
    return {
        "role_created": bool(created_roles),
        "added": added,
        "missing_usernames": [],
        "member_usernames": [u.username for u in users],
        "member_names": [u.real_name or u.username for u in users],
    }


# 生产卡物料编码角色「1.2.8生产卡/补充流程-物料编码」：韩青芳、司子潆、郭雪
# （产线/单机物料编码节点仍是海淼、段云云具名，勿与此角色混淆）
PROD_MATERIAL_CODE_MEMBER_USERNAMES: tuple[str, ...] = (
    "02366236281651",  # 韩青芳
    "010624465121410798",  # 司子潆
    "45424060301188765",  # 郭雪
)
PROD_MATERIAL_CODE_MEMBER_REAL_NAMES: tuple[str, ...] = ("韩青芳", "司子潆", "郭雪")


async def ensure_prod_material_code_role_members(db, tenant_id: str) -> dict:
    """确保 prod_material_code 成员仅为韩青芳/司子潆/郭雪。"""
    from app.domains.auth.models import User, UserRole

    result = await _ensure_role_members(
        db,
        tenant_id,
        "prod_material_code",
        PROD_MATERIAL_CODE_MEMBER_USERNAMES,
        PROD_MATERIAL_CODE_MEMBER_REAL_NAMES,
    )
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "prod_material_code")
        )
    ).scalar_one_or_none()
    if not role:
        return result

    keep_users = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.username.in_(list(PROD_MATERIAL_CODE_MEMBER_USERNAMES)),
            )
        )
    ).scalars().all()
    keep_ids = set(keep_users)
    by_real = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.real_name.in_(list(PROD_MATERIAL_CODE_MEMBER_REAL_NAMES)),
                User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    keep_ids.update(by_real)

    if keep_ids:
        pruned = await db.execute(
            sa_delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == role.id,
                UserRole.user_id.notin_(list(keep_ids)),
            )
        )
        result["pruned"] = int(pruned.rowcount or 0)
    else:
        result["pruned"] = 0
    result["role_name"] = role.name
    return result


# 简道云「1.2.8生产卡/补充流程-电气车间」：李同民、张雨辰
PROD_ELEC_WORKSHOP_MEMBER_USERNAMES: tuple[str, ...] = (
    "02364337364933",  # 李同民
    "446440225824636648",  # 张雨辰
)
PROD_ELEC_WORKSHOP_MEMBER_REAL_NAMES: tuple[str, ...] = ("李同民", "张雨辰")


async def ensure_prod_elec_workshop_role_members(db, tenant_id: str) -> dict:
    """确保 prod_elec_workshop 成员仅为李同民、张雨辰。"""
    from app.domains.auth.models import User, UserRole

    result = await _ensure_role_members(
        db,
        tenant_id,
        "prod_elec_workshop",
        PROD_ELEC_WORKSHOP_MEMBER_USERNAMES,
        PROD_ELEC_WORKSHOP_MEMBER_REAL_NAMES,
    )
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "prod_elec_workshop")
        )
    ).scalar_one_or_none()
    if not role:
        return result

    keep_users = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.username.in_(list(PROD_ELEC_WORKSHOP_MEMBER_USERNAMES)),
            )
        )
    ).scalars().all()
    keep_ids = set(keep_users)
    by_real = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.real_name.in_(list(PROD_ELEC_WORKSHOP_MEMBER_REAL_NAMES)),
                User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    keep_ids.update(by_real)

    if keep_ids:
        pruned = await db.execute(
            sa_delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == role.id,
                UserRole.user_id.notin_(list(keep_ids)),
            )
        )
        result["pruned"] = int(pruned.rowcount or 0)
    else:
        result["pruned"] = 0
    result["role_name"] = role.name
    return result


# 简道云「24.2.3合同/项目评审-法务审批多人」：杜习慧、孔雪、张孟杰
LEGAL_MEMBER_USERNAMES: tuple[str, ...] = (
    "543355140326074979",  # 杜习慧
    "4723152427763414",  # 孔雪
    "256932256424153873",  # 张孟杰
)
LEGAL_MEMBER_REAL_NAMES: tuple[str, ...] = ("杜习慧", "孔雪", "张孟杰")


async def ensure_legal_role_members(db, tenant_id: str) -> dict:
    """确保 legal=24.2.3合同/项目评审-法务审批多人，成员杜习慧/孔雪/张孟杰。"""
    from app.domains.auth.models import User, UserRole

    result = await _ensure_role_members(
        db,
        tenant_id,
        "legal",
        LEGAL_MEMBER_USERNAMES,
        LEGAL_MEMBER_REAL_NAMES,
    )
    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "legal")
        )
    ).scalar_one_or_none()
    if not role:
        return result

    keep_users = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.username.in_(list(LEGAL_MEMBER_USERNAMES)),
            )
        )
    ).scalars().all()
    keep_ids = set(keep_users)
    # 姓名兜底（username 未对齐钉钉时）
    by_real = (
        await db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.real_name.in_(list(LEGAL_MEMBER_REAL_NAMES)),
                User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    keep_ids.update(by_real)

    if keep_ids:
        pruned = await db.execute(
            sa_delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == role.id,
                UserRole.user_id.notin_(list(keep_ids)),
            )
        )
        result["pruned"] = int(pruned.rowcount or 0)
    else:
        result["pruned"] = 0
    result["role_name"] = role.name
    return result


PROD_QUALITY_CONTROL_DEPT_NAMES: tuple[str, ...] = ("工艺与质量控制部",)
PLAN_PROCUREMENT_DEPT_NAMES: tuple[str, ...] = ("计划采购部",)
PLAN_DISPATCH_DEPT_NAMES: tuple[str, ...] = ("计划调度室",)


async def ensure_prod_quality_control_dept_role(db, tenant_id: str) -> dict:
    """确保 prod_quality_control 角色存在，并通过部门规则挂给工艺与质量控制部成员。"""
    from app.domains.auth.service import invalidate_tenant_auth_cache
    from app.common.dept_role_auto import apply_dept_role_rules_bulk
    from app.domains.organization.models import Department, DeptRoleRule

    await ensure_business_roles(db, tenant_id, ["prod_quality_control"])
    role = (
        await db.execute(
            select(Role).where(
                Role.tenant_id == tenant_id, Role.code == "prod_quality_control",
            )
        )
    ).scalar_one_or_none()
    if not role:
        return {"error": "role_not_found"}

    depts = (
        await db.execute(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.name.in_(PROD_QUALITY_CONTROL_DEPT_NAMES),
            )
        )
    ).scalars().all()

    rules_added = 0
    for d in depts:
        exists = (
            await db.execute(
                select(DeptRoleRule.id).where(
                    DeptRoleRule.tenant_id == tenant_id,
                    DeptRoleRule.department_id == d.id,
                    DeptRoleRule.role_id == role.id,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(DeptRoleRule(
            id=generate_uuid(),
            tenant_id=tenant_id,
            department_id=d.id,
            role_id=role.id,
            include_children=True,
            enabled=True,
        ))
        rules_added += 1
    await db.flush()

    stats = await apply_dept_role_rules_bulk(db, tenant_id, commit=False)
    await invalidate_tenant_auth_cache(tenant_id)
    return {
        "role_code": role.code,
        "role_name": role.name,
        "scope_by_resource": dict(role.scope_by_resource or {}),
        "dept_rules_added": rules_added,
        "depts": [{"id": d.id, "name": d.name, "path": d.path} for d in depts],
        "apply": stats,
    }


async def ensure_plan_procurement_dept_role(db, tenant_id: str) -> dict:
    """确保 plan_procurement_dept 角色存在，并通过部门规则挂给计划采购部成员。"""
    from app.domains.auth.service import invalidate_tenant_auth_cache
    from app.common.dept_role_auto import apply_dept_role_rules_bulk
    from app.domains.organization.models import Department, DeptRoleRule

    await ensure_business_roles(db, tenant_id, ["plan_procurement_dept"])
    role = (
        await db.execute(
            select(Role).where(
                Role.tenant_id == tenant_id, Role.code == "plan_procurement_dept",
            )
        )
    ).scalar_one_or_none()
    if not role:
        return {"error": "role_not_found"}

    depts = (
        await db.execute(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.name.in_(PLAN_PROCUREMENT_DEPT_NAMES),
            )
        )
    ).scalars().all()

    rules_added = 0
    for d in depts:
        exists = (
            await db.execute(
                select(DeptRoleRule.id).where(
                    DeptRoleRule.tenant_id == tenant_id,
                    DeptRoleRule.department_id == d.id,
                    DeptRoleRule.role_id == role.id,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(DeptRoleRule(
            id=generate_uuid(),
            tenant_id=tenant_id,
            department_id=d.id,
            role_id=role.id,
            include_children=True,
            enabled=True,
        ))
        rules_added += 1
    await db.flush()

    stats = await apply_dept_role_rules_bulk(db, tenant_id, commit=False)
    await invalidate_tenant_auth_cache(tenant_id)
    return {
        "role_code": role.code,
        "role_name": role.name,
        "scope_by_resource": dict(role.scope_by_resource or {}),
        "dept_rules_added": rules_added,
        "depts": [{"id": d.id, "name": d.name, "path": d.path} for d in depts],
        "apply": stats,
    }


async def ensure_plan_dispatch_dept_role(db, tenant_id: str) -> dict:
    """确保 plan_dispatch_dept 角色存在，并通过部门规则挂给计划调度室成员。"""
    from app.domains.auth.service import invalidate_tenant_auth_cache
    from app.common.dept_role_auto import apply_dept_role_rules_bulk
    from app.domains.organization.models import Department, DeptRoleRule

    await ensure_business_roles(db, tenant_id, ["plan_dispatch_dept"])
    role = (
        await db.execute(
            select(Role).where(
                Role.tenant_id == tenant_id, Role.code == "plan_dispatch_dept",
            )
        )
    ).scalar_one_or_none()
    if not role:
        return {"error": "role_not_found"}

    depts = (
        await db.execute(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.name.in_(PLAN_DISPATCH_DEPT_NAMES),
            )
        )
    ).scalars().all()

    rules_added = 0
    for d in depts:
        exists = (
            await db.execute(
                select(DeptRoleRule.id).where(
                    DeptRoleRule.tenant_id == tenant_id,
                    DeptRoleRule.department_id == d.id,
                    DeptRoleRule.role_id == role.id,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(DeptRoleRule(
            id=generate_uuid(),
            tenant_id=tenant_id,
            department_id=d.id,
            role_id=role.id,
            include_children=True,
            enabled=True,
        ))
        rules_added += 1
    await db.flush()

    stats = await apply_dept_role_rules_bulk(db, tenant_id, commit=False)
    await invalidate_tenant_auth_cache(tenant_id)
    return {
        "role_code": role.code,
        "role_name": role.name,
        "scope_by_resource": dict(role.scope_by_resource or {}),
        "dept_rules_added": rules_added,
        "depts": [{"id": d.id, "name": d.name, "path": d.path} for d in depts],
        "apply": stats,
    }


async def ensure_nine_flow_role_members(db, tenant_id: str) -> dict:
    """九流程审批角色：创建目录角色并挂成员。"""
    await ensure_business_roles(db, tenant_id)
    return {
        "room_leader": await ensure_room_leader_role_members(db, tenant_id),
        "transfer_packaging": await ensure_transfer_packaging_role_members(db, tenant_id),
        "cs_office": await ensure_cs_office_role_members(db, tenant_id),
        "cs_arrange": await ensure_cs_arrange_role_members(db, tenant_id),
        "cs_delay_approve": await ensure_cs_delay_approve_role_members(db, tenant_id),
        "logistics_approval": await ensure_logistics_approval_role_members(db, tenant_id),
        "ship_sales_outbound": await ensure_ship_sales_outbound_role_members(db, tenant_id),
        "gate_guard": await ensure_gate_guard_role_members(db, tenant_id),
        "prod_material_code": await ensure_prod_material_code_role_members(db, tenant_id),
        "prod_elec_workshop": await ensure_prod_elec_workshop_role_members(db, tenant_id),
        "legal": await ensure_legal_role_members(db, tenant_id),
    }


FUJIAJING_JDY_ROLE_CODES = (
    "cs_office",
    "cs_arrange",
    "cs_named_fjj_zdd_jw",
    "cs_service_cc",
    "cs_replace_trace",
    "cs_special_release",
    "cs_service_record",
    "trip_overtime_init15",
    "loan_eng_mgmt",
    "biz_backoffice",
    "jdy_sub_admin",
)


async def ensure_cs_customer_scope_roles(db, tenant_id: str) -> list[str]:
    """客服相关角色：补 scope_by_resource.customer=all（客户列表看全部）。"""
    from app.common.rbac_catalog import CS_CUSTOMER_ALL_ROLE_CODES

    return await ensure_business_roles(db, tenant_id, sorted(CS_CUSTOMER_ALL_ROLE_CODES))


async def ensure_fujiajing_jdy_role_members(
    db,
    tenant_id: str,
    by_crm_code: dict[str, dict],
) -> dict:
    """按简道云成员 JSON（by_crm_code）创建缺失角色并挂成员（仅 additive）。"""
    codes = [c for c in FUJIAJING_JDY_ROLE_CODES if c in by_crm_code]
    created_roles = await ensure_business_roles(db, tenant_id, codes)
    out: dict = {"created_roles": created_roles, "roles": {}}
    for code in codes:
        info = by_crm_code.get(code) or {}
        members = info.get("members") or []
        usernames = tuple(
            str(m.get("username") or "").strip()
            for m in members
            if str(m.get("username") or "").strip()
        )
        real_names = tuple(
            str(m.get("name") or "").strip()
            for m in members
            if str(m.get("name") or "").strip()
        )
        if code == "cs_arrange":
            out["roles"][code] = await ensure_cs_arrange_role_members(db, tenant_id)
            continue
        if code == "cs_office":
            out["roles"][code] = await _ensure_role_members(
                db,
                tenant_id,
                code,
                usernames,
                real_names,
            )
            continue
        out["roles"][code] = await _ensure_role_members(
            db,
            tenant_id,
            code,
            usernames,
            real_names,
        )
    return out


async def ensure_wf_assignees_have_form_view(db, tenant_id: str) -> dict:
    """流程任务处理人若缺 form_data:view，补挂 employee 基础角色（含 CORE）。"""
    from app.domains.auth.models import UserRole, Role, Permission, RolePermission
    from app.domains.lowcode.workflow_models import WfTaskInstance

    employee = (await db.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.code == "employee")
    )).scalar_one_or_none()
    if not employee:
        await ensure_business_roles(db, tenant_id, ["employee"])
        employee = (await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "employee")
        )).scalar_one_or_none()
    if not employee:
        return {"patched": 0, "reason": "no_employee_role"}

    assignee_ids = list({
        uid for uid in (await db.execute(
            select(WfTaskInstance.assignee_id).distinct()
        )).scalars().all() if uid
    })
    if not assignee_ids:
        return {"patched": 0}

    patched = 0
    for uid in assignee_ids:
        has_fdv = (await db.execute(
            select(RolePermission.id).join(UserRole, UserRole.role_id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                UserRole.user_id == uid,
                UserRole.tenant_id == tenant_id,
                Permission.code == "form_data:view",
            ).limit(1)
        )).scalar_one_or_none()
        if has_fdv:
            continue
        has_employee = (await db.execute(
            select(UserRole.id).where(
                UserRole.user_id == uid,
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == employee.id,
            ).limit(1)
        )).scalar_one_or_none()
        if not has_employee:
            db.add(UserRole(
                id=generate_uuid(),
                tenant_id=tenant_id,
                user_id=uid,
                role_id=employee.id,
            ))
            patched += 1
    if patched:
        from app.domains.auth.service import invalidate_tenant_auth_cache
        await invalidate_tenant_auth_cache(tenant_id)
    return {"patched": patched, "assignees_scanned": len(assignee_ids)}


async def ensure_approval_roles_list_access(db, tenant_id: str) -> dict:
    """审批相关角色/人员：同步 CORE 权限、业务角色 scope、九流程成员、任务处理人 form_data:view。"""
    rbac_result = await apply(db, tenant_id, mode="additive", create_missing_roles=True)
    biz_created = await ensure_business_roles(db, tenant_id)
    nine = await ensure_nine_flow_role_members(db, tenant_id)
    cs = await ensure_cs_customer_scope_roles(db, tenant_id)
    assignees = await ensure_wf_assignees_have_form_view(db, tenant_id)
    return {
        "rbac": rbac_result,
        "business_roles_created": biz_created,
        "nine_flow": nine,
        "cs_scope_roles": cs,
        "wf_assignees": assignees,
    }
