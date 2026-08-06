# -*- coding: utf-8 -*-
"""可选范围解析与 CRUD。"""
from __future__ import annotations

from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR, DUPLICATE_ENTRY
from app.common.dept_tree import subtree_dept_ids_select
from app.database import generate_uuid
from app.domains.auth.models import User, Role, UserRole
from app.domains.organization.models import Department, UserDepartment
from app.domains.organization.pickable_scope_models import PickableScope

# 预置范围：成员在「可选范围」页直接勾选
PRESET_SCOPES = [
    {
        "code": "room_leaders",
        "name": "方案管理-设计指派",
        "kind": "person",
        "description": "方案管理「设计指派」人选范围；在此直接勾选成员。",
        "is_system": True,
        "rules": {"role_codes": [], "user_ids": [], "dept_ids": [], "include_children": True},
    },
    {
        "code": "scheme_offices",
        "name": "方案管理-科室",
        "kind": "department",
        "description": "方案管理「科室」可选部门范围。",
        "is_system": True,
        "rules": {"role_codes": [], "user_ids": [], "dept_ids": [], "include_children": True},
    },
    {
        "code": "fa-zxxgy",
        "name": "方案管理-转新乡、工艺包装",
        "kind": "person",
        "description": "方案管理「转新乡、工艺包装」人选范围；在此直接勾选成员。",
        "is_system": True,
        "rules": {"role_codes": [], "user_ids": [], "dept_ids": [], "include_children": True},
    },
]


def _rules(scope: PickableScope | dict) -> dict:
    if isinstance(scope, dict):
        r = scope.get("rules") or {}
    else:
        r = scope.rules or {}
    return r if isinstance(r, dict) else {}


async def _flatten_role_rules_to_users(
    db: AsyncSession, tenant_id: str, scope: PickableScope,
) -> bool:
    """把旧版「按角色」规则摊平成人员列表，方便管理员直接勾选。"""
    r = _rules(scope)
    role_codes = [str(c) for c in (r.get("role_codes") or []) if c]
    if not role_codes:
        return False
    from_roles = await _user_ids_in_roles(db, tenant_id, role_codes)
    user_ids = {str(u) for u in (r.get("user_ids") or []) if u} | from_roles
    scope.rules = {
        "role_codes": [],
        "user_ids": sorted(user_ids),
        "dept_ids": [],
        "include_children": True,
    }
    preset = next((p for p in PRESET_SCOPES if p["code"] == scope.code), None)
    if preset and preset.get("description"):
        scope.description = preset["description"]
    return True


async def ensure_preset_scopes(db: AsyncSession, tenant_id: str) -> list[str]:
    """确保预置可选范围存在；并把旧 role_codes 规则摊平成人员。返回新建的 code。"""
    existing_rows = list(
        (
            await db.execute(
                select(PickableScope).where(
                    PickableScope.tenant_id == tenant_id,
                    PickableScope.code.in_([p["code"] for p in PRESET_SCOPES]),
                )
            )
        ).scalars().all()
    )
    existing = {s.code: s for s in existing_rows}
    created: list[str] = []
    changed = False
    for p in PRESET_SCOPES:
        row = existing.get(p["code"])
        if row:
            if row.name != p["name"]:
                row.name = p["name"]
                changed = True
            if p.get("description") and row.description != p.get("description"):
                row.description = p.get("description")
                changed = True
            continue
        db.add(PickableScope(
            id=generate_uuid(),
            tenant_id=tenant_id,
            code=p["code"],
            name=p["name"],
            kind=p["kind"],
            description=p.get("description"),
            is_system=bool(p.get("is_system")),
            rules=dict(p.get("rules") or {}),
        ))
        created.append(p["code"])
    if created or changed:
        await db.flush()

    # 所有人员范围：若仍绑角色，摊平成 user_ids（含预置与历史数据）
    person_scopes = list(
        (
            await db.execute(
                select(PickableScope).where(
                    PickableScope.tenant_id == tenant_id,
                    PickableScope.kind == "person",
                )
            )
        ).scalars().all()
    )
    for s in person_scopes:
        if await _flatten_role_rules_to_users(db, tenant_id, s):
            changed = True
    if changed:
        await db.flush()
    return created


async def list_scopes(
    db: AsyncSession, tenant_id: str, kind: str | None = None,
) -> list[PickableScope]:
    await ensure_preset_scopes(db, tenant_id)
    q = select(PickableScope).where(PickableScope.tenant_id == tenant_id)
    if kind:
        q = q.where(PickableScope.kind == kind)
    q = q.order_by(PickableScope.is_system.desc(), PickableScope.name)
    return list((await db.execute(q)).scalars().all())


async def get_scope_by_id(db: AsyncSession, tenant_id: str, scope_id: str) -> PickableScope:
    s = (await db.execute(
        select(PickableScope).where(
            PickableScope.id == scope_id, PickableScope.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not s:
        raise BusinessException(code=NOT_FOUND, message="可选范围不存在")
    return s


async def get_scope_by_code(db: AsyncSession, tenant_id: str, code: str) -> PickableScope | None:
    return (await db.execute(
        select(PickableScope).where(
            PickableScope.tenant_id == tenant_id, PickableScope.code == code,
        )
    )).scalar_one_or_none()


async def create_scope(
    db: AsyncSession, tenant_id: str, *,
    code: str, name: str, kind: str, description: str | None, rules: dict | None,
) -> PickableScope:
    code = (code or "").strip()
    name = (name or "").strip()
    kind = (kind or "person").strip()
    if not code or not name:
        raise BusinessException(code=VALIDATION_ERROR, message="编码和名称不能为空")
    if kind not in ("person", "department"):
        raise BusinessException(code=VALIDATION_ERROR, message="类型须为 person 或 department")
    if await get_scope_by_code(db, tenant_id, code):
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"编码已存在: {code}")
    s = PickableScope(
        id=generate_uuid(), tenant_id=tenant_id, code=code, name=name, kind=kind,
        description=description, is_system=False, rules=dict(rules or {}),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def update_scope(
    db: AsyncSession, tenant_id: str, scope_id: str, *,
    name: str | None = None, description: str | None = None, rules: dict | None = None,
) -> PickableScope:
    s = await get_scope_by_id(db, tenant_id, scope_id)
    if name is not None:
        s.name = name.strip() or s.name
    if description is not None:
        s.description = description
    if rules is not None:
        if not isinstance(rules, dict):
            raise BusinessException(code=VALIDATION_ERROR, message="rules 须为对象")
        s.rules = dict(rules)
    await db.commit()
    await db.refresh(s)
    return s


async def delete_scope(db: AsyncSession, tenant_id: str, scope_id: str) -> None:
    s = await get_scope_by_id(db, tenant_id, scope_id)
    if s.is_system:
        raise BusinessException(message="系统预置范围不能删除，可编辑成员")
    await db.execute(
        delete(PickableScope).where(
            PickableScope.id == scope_id, PickableScope.tenant_id == tenant_id,
        )
    )
    await db.commit()


async def _user_ids_in_roles(db: AsyncSession, tenant_id: str, role_codes: list[str]) -> set[str]:
    if not role_codes:
        return set()
    role_ids = (
        await db.execute(
            select(Role.id).where(Role.tenant_id == tenant_id, Role.code.in_(role_codes))
        )
    ).scalars().all()
    if not role_ids:
        return set()
    return set(
        (
            await db.execute(
                select(UserRole.user_id).where(
                    UserRole.tenant_id == tenant_id, UserRole.role_id.in_(role_ids),
                )
            )
        ).scalars().all()
    )


async def _user_ids_in_depts(
    db: AsyncSession, tenant_id: str, dept_ids: list[str], include_children: bool = True,
) -> set[str]:
    if not dept_ids:
        return set()
    if include_children:
        rows = (
            await db.execute(
                select(Department.id, Department.path).where(
                    Department.tenant_id == tenant_id, Department.id.in_(dept_ids),
                )
            )
        ).all()
        if not rows:
            return set()
        subtree = subtree_dept_ids_select(
            tenant_id, [r[0] for r in rows], [r[1] for r in rows],
        )
        target_depts = subtree
    else:
        target_depts = select(Department.id).where(
            Department.tenant_id == tenant_id, Department.id.in_(dept_ids),
        )
    return set(
        (
            await db.execute(
                select(UserDepartment.user_id).where(
                    UserDepartment.tenant_id == tenant_id,
                    UserDepartment.department_id.in_(target_depts),
                )
            )
        ).scalars().all()
    )


async def resolve_person_ids(
    db: AsyncSession, tenant_id: str, scope: PickableScope | dict,
    extra_dept_ids: list[str] | None = None,
) -> set[str] | None:
    """解析人员范围。返回 None 表示不限制；空 set 表示范围内无人。"""
    r = _rules(scope)
    role_codes = [str(c) for c in (r.get("role_codes") or []) if c]
    user_ids = [str(u) for u in (r.get("user_ids") or []) if u]
    dept_ids = [str(d) for d in (r.get("dept_ids") or []) if d]
    include_children = r.get("include_children") is not False

    has_any = bool(role_codes or user_ids or dept_ids)
    if not has_any:
        # 人员范围未勾选任何人 → 无人可选（绑了范围就不能误放开全员）
        kind = scope.get("kind") if isinstance(scope, dict) else getattr(scope, "kind", None)
        if kind == "person":
            return set()
        ids = None
    else:
        ids = set()
        if role_codes:
            ids |= await _user_ids_in_roles(db, tenant_id, role_codes)
        if user_ids:
            ids |= set(user_ids)
        if dept_ids:
            ids |= await _user_ids_in_depts(db, tenant_id, dept_ids, include_children)

    if extra_dept_ids:
        in_dept = await _user_ids_in_depts(db, tenant_id, list(extra_dept_ids), True)
        if ids is None:
            ids = in_dept
        else:
            ids &= in_dept
    return ids


async def resolve_department_ids(
    db: AsyncSession, tenant_id: str, scope: PickableScope | dict,
) -> set[str] | None:
    """解析部门范围。None=不限制。"""
    r = _rules(scope)
    dept_ids = [str(d) for d in (r.get("dept_ids") or []) if d]
    if not dept_ids:
        return None
    include_children = r.get("include_children") is not False
    if not include_children:
        return set(dept_ids)
    rows = (
        await db.execute(
            select(Department.id, Department.path).where(
                Department.tenant_id == tenant_id, Department.id.in_(dept_ids),
            )
        )
    ).all()
    if not rows:
        return set()
    subtree = subtree_dept_ids_select(
        tenant_id, [r0[0] for r0 in rows], [r0[1] for r0 in rows],
    )
    return set((await db.execute(subtree)).scalars().all())


def scope_to_dict(s: PickableScope) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "kind": s.kind,
        "description": s.description,
        "is_system": s.is_system,
        "rules": s.rules or {},
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
