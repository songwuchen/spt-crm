import re
import csv
import io
import bcrypt
from sqlalchemy import select, func, delete, false
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.dept_tree import LIKE_ESCAPE, escape_like, subtree_dept_ids_select
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, DUPLICATE_ENTRY
from app.domains.organization.models import Department, UserDepartment, DeptRoleRule
from app.domains.auth.models import User, Role, UserRole, RolePermission, Permission
from app.domains.organization.schemas import (
    DepartmentCreate, DepartmentUpdate, UserCreate, UserUpdate, RoleCreate, GrantPermissions,
    DeptRoleRuleCreate, DeptRoleRuleUpdate,
)


# ==================== Department ====================

async def get_department_tree(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(Department).where(Department.tenant_id == tenant_id).order_by(Department.sort_order)
    )
    all_depts = result.scalars().all()

    dept_map = {d.id: d for d in all_depts}
    roots = []
    for d in all_depts:
        d._children = []
    for d in all_depts:
        if d.parent_id and d.parent_id in dept_map:
            dept_map[d.parent_id]._children.append(d)
        else:
            roots.append(d)

    def to_dict(d):
        return {
            "id": d.id, "name": d.name, "parent_id": d.parent_id,
            "path": d.path, "sort_order": d.sort_order, "leader_id": d.leader_id,
            "children": [to_dict(c) for c in d._children],
        }

    return [to_dict(r) for r in roots]


async def create_department(db: AsyncSession, tenant_id: str, data: DepartmentCreate) -> Department:
    parent_path = "/"
    if data.parent_id:
        parent = (await db.execute(
            select(Department).where(Department.id == data.parent_id, Department.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not parent:
            raise BusinessException(code=NOT_FOUND, message="父部门不存在")
        parent_path = parent.path if parent.path.endswith("/") else parent.path + "/"

    dept = Department(
        id=generate_uuid(), tenant_id=tenant_id,
        name=data.name, parent_id=data.parent_id,
        path=parent_path + data.name + "/",
        sort_order=data.sort_order, leader_id=data.leader_id,
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


async def update_department(db: AsyncSession, tenant_id: str, dept_id: str, data: DepartmentUpdate) -> Department:
    dept = (await db.execute(
        select(Department).where(Department.id == dept_id, Department.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not dept:
        raise BusinessException(code=NOT_FOUND, message="部门不存在")

    old_path = dept.path
    update_data = data.model_dump(exclude_unset=True)
    name_changed = "name" in update_data and update_data["name"] != dept.name
    parent_changed = "parent_id" in update_data and update_data["parent_id"] != dept.parent_id

    for field, val in update_data.items():
        setattr(dept, field, val)

    # Recompute path if name or parent changed
    if name_changed or parent_changed:
        new_parent_path = "/"
        if dept.parent_id:
            parent = (await db.execute(
                select(Department).where(Department.id == dept.parent_id, Department.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if not parent:
                raise BusinessException(code=NOT_FOUND, message="父部门不存在")
            new_parent_path = parent.path if parent.path.endswith("/") else parent.path + "/"
        new_path = new_parent_path + dept.name + "/"
        dept.path = new_path

        # Cascade update all descendant paths
        if old_path != new_path:
            descendants = (await db.execute(
                select(Department).where(
                    Department.tenant_id == tenant_id,
                    Department.path.like(old_path + "%"),
                    Department.id != dept_id,
                )
            )).scalars().all()
            for child in descendants:
                child.path = new_path + child.path[len(old_path):]

    await db.commit()
    await db.refresh(dept)
    return dept


async def delete_department(db: AsyncSession, tenant_id: str, dept_id: str):
    dept = (await db.execute(
        select(Department).where(Department.id == dept_id, Department.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not dept:
        raise BusinessException(code=NOT_FOUND, message="部门不存在")

    # Check children
    children = (await db.execute(
        select(func.count(Department.id)).where(Department.parent_id == dept_id, Department.tenant_id == tenant_id)
    )).scalar()
    if children > 0:
        raise BusinessException(message="请先删除子部门")

    # 清理引用该部门的「部门→角色」规则，避免外键冲突
    await db.execute(delete(DeptRoleRule).where(
        DeptRoleRule.department_id == dept_id, DeptRoleRule.tenant_id == tenant_id
    ))
    await db.delete(dept)
    await db.commit()


# ==================== User ====================

async def get_user(db: AsyncSession, tenant_id: str, user_id: str) -> User:
    user = (await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user:
        raise BusinessException(code=NOT_FOUND, message="用户不存在")
    return user


async def list_users(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None,
    role_id: str | None = None,
    dept_id: str | None = None,
    is_active: bool | None = None,
):
    base = select(User).where(User.tenant_id == tenant_id)
    if keyword:
        # 转义 LIKE 元字符，否则搜 "_" / "50%" 会当成通配符命中一大片
        kw = f"%{escape_like(keyword)}%"
        base = base.where(
            User.real_name.ilike(kw, escape=LIKE_ESCAPE)
            | User.username.ilike(kw, escape=LIKE_ESCAPE)
            | User.phone.ilike(kw, escape=LIKE_ESCAPE)
            | User.email.ilike(kw, escape=LIKE_ESCAPE)
        )
    if role_id:
        base = base.where(User.id.in_(
            select(UserRole.user_id).where(
                UserRole.role_id == role_id, UserRole.tenant_id == tenant_id
            )
        ))
    if dept_id:
        # 选中某部门时连同其所有下级部门的成员一起返回（物化路径前缀匹配）
        dept = (await db.execute(select(Department).where(
            Department.id == dept_id, Department.tenant_id == tenant_id
        ))).scalar_one_or_none()
        if dept is None:
            base = base.where(false())
        else:
            base = base.where(User.id.in_(
                select(UserDepartment.user_id).where(
                    UserDepartment.tenant_id == tenant_id,
                    UserDepartment.department_id.in_(
                        subtree_dept_ids_select(tenant_id, [dept.id], [dept.path])
                    ),
                )
            ))
    if is_active is not None:
        base = base.where(User.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(base.order_by(User.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return items, total


async def _validate_role_dept_ids(
    db: AsyncSession, tenant_id: str,
    role_ids: list[str] | None, department_ids: list[str] | None,
) -> None:
    """Ensure every role/department id belongs to this tenant before linking it to a user.

    Prevents cross-tenant role injection (a caller attaching another tenant's role, which
    would leak that role's permissions) and surfaces a clean error instead of a downstream
    FK IntegrityError when an id does not exist at all.
    """
    if role_ids:
        valid = set((await db.execute(
            select(Role.id).where(Role.id.in_(role_ids), Role.tenant_id == tenant_id)
        )).scalars().all())
        invalid = set(role_ids) - valid
        if invalid:
            raise BusinessException(message=f"角色不存在或不属于当前租户: {', '.join(invalid)}")
    if department_ids:
        valid = set((await db.execute(
            select(Department.id).where(Department.id.in_(department_ids), Department.tenant_id == tenant_id)
        )).scalars().all())
        invalid = set(department_ids) - valid
        if invalid:
            raise BusinessException(message=f"部门不存在或不属于当前租户: {', '.join(invalid)}")


async def create_user(db: AsyncSession, tenant_id: str, data: UserCreate) -> User:
    existing = (await db.execute(
        select(User).where(User.username == data.username, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"用户名 {data.username} 已存在")

    await _validate_role_dept_ids(db, tenant_id, data.role_ids, data.department_ids)

    user = User(
        id=generate_uuid(), tenant_id=tenant_id,
        username=data.username, password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode(),
        real_name=data.real_name, phone=data.phone, email=data.email,
    )
    db.add(user)

    for rid in data.role_ids:
        db.add(UserRole(id=generate_uuid(), tenant_id=tenant_id, user_id=user.id, role_id=rid))
    for did in data.department_ids:
        db.add(UserDepartment(id=generate_uuid(), tenant_id=tenant_id, user_id=user.id, department_id=did))

    try:
        await db.commit()
    except IntegrityError:
        # Lost a race against a concurrent create with the same (tenant_id, username);
        # the uq_user_tenant_username constraint protected the data — return a clean message.
        await db.rollback()
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"用户名 {data.username} 已存在")
    await db.refresh(user)
    # 按「部门→角色」规则自动补角色(仅新增，不覆盖显式传入的角色)
    from app.common.dept_role_auto import apply_dept_role_rules
    await apply_dept_role_rules(db, tenant_id, user.id)
    return user


async def update_user(db: AsyncSession, tenant_id: str, user_id: str, data: UserUpdate) -> User:
    user = (await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user:
        raise BusinessException(code=NOT_FOUND, message="用户不存在")

    update_data = data.model_dump(exclude_unset=True)
    role_ids = update_data.pop("role_ids", None)
    department_ids = update_data.pop("department_ids", None)

    await _validate_role_dept_ids(db, tenant_id, role_ids, department_ids)

    for field, val in update_data.items():
        setattr(user, field, val)

    if role_ids is not None:
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id))
        for rid in role_ids:
            db.add(UserRole(id=generate_uuid(), tenant_id=tenant_id, user_id=user_id, role_id=rid))

    # 只有部门集合「实际发生变化」时才触发自动补角色——避免仅改手机号/姓名(前端把
    # 当前部门原样回传)时，把管理员刚手工去掉的角色又加回来。
    depts_changed = False
    if department_ids is not None:
        old_dept_ids = set((await db.execute(
            select(UserDepartment.department_id).where(
                UserDepartment.user_id == user_id, UserDepartment.tenant_id == tenant_id)
        )).scalars().all())
        depts_changed = old_dept_ids != set(department_ids)
        await db.execute(delete(UserDepartment).where(UserDepartment.user_id == user_id, UserDepartment.tenant_id == tenant_id))
        for did in department_ids:
            db.add(UserDepartment(id=generate_uuid(), tenant_id=tenant_id, user_id=user_id, department_id=did))

    await db.commit()
    await db.refresh(user)
    # 部门确有变更后，按「部门→角色」规则自动补角色(仅新增)。
    # 内部会自行失效缓存；置于 role 缓存失效之前避免重复。
    if depts_changed:
        from app.common.dept_role_auto import apply_dept_role_rules
        await apply_dept_role_rules(db, tenant_id, user_id)
    # 角色变更后失效该用户的权限/角色缓存，使其重新登录立即生效（issue #49）
    if role_ids is not None:
        from app.domains.auth.service import invalidate_user_auth_cache
        await invalidate_user_auth_cache(user_id, tenant_id)
    return user


async def bulk_set_roles(db: AsyncSession, tenant_id: str, user_ids: list[str], role_ids: list[str], mode: str = "replace") -> int:
    """批量给多个用户设置角色。mode=replace 覆盖、add 追加。返回受影响用户数。"""
    await _validate_role_dept_ids(db, tenant_id, role_ids, None)
    valid_ids = set((await db.execute(
        select(User.id).where(User.tenant_id == tenant_id, User.id.in_(user_ids))
    )).scalars().all())
    if not valid_ids:
        return 0

    if mode == "add":
        existing = {
            (ur.user_id, ur.role_id)
            for ur in (await db.execute(
                select(UserRole).where(UserRole.tenant_id == tenant_id, UserRole.user_id.in_(valid_ids))
            )).scalars().all()
        }
        for uid in valid_ids:
            for rid in role_ids:
                if (uid, rid) not in existing:
                    db.add(UserRole(id=generate_uuid(), tenant_id=tenant_id, user_id=uid, role_id=rid))
    else:  # replace
        await db.execute(delete(UserRole).where(UserRole.tenant_id == tenant_id, UserRole.user_id.in_(valid_ids)))
        for uid in valid_ids:
            for rid in role_ids:
                db.add(UserRole(id=generate_uuid(), tenant_id=tenant_id, user_id=uid, role_id=rid))

    await db.commit()
    # 失效受影响用户的权限/角色缓存（issue #49）
    from app.domains.auth.service import invalidate_user_auth_cache
    for uid in valid_ids:
        await invalidate_user_auth_cache(uid, tenant_id)
    return len(valid_ids)


async def delete_user(db: AsyncSession, tenant_id: str, user_id: str, current_user_id: str):
    user = (await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user:
        raise BusinessException(code=NOT_FOUND, message="用户不存在")
    if user_id == current_user_id:
        raise BusinessException(message="不能删除当前登录用户")
    # 清理对 users.id 有外键约束的关联记录，避免删除时外键冲突 500
    from app.domains.auth.models import LoginSession
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id))
    await db.execute(delete(UserDepartment).where(UserDepartment.user_id == user_id, UserDepartment.tenant_id == tenant_id))
    await db.execute(delete(LoginSession).where(LoginSession.user_id == user_id, LoginSession.tenant_id == tenant_id))
    await db.delete(user)
    await db.commit()
    from app.domains.auth.service import invalidate_user_auth_cache
    await invalidate_user_auth_cache(user_id, tenant_id)


async def import_users(db: AsyncSession, tenant_id: str, rows: list) -> dict:
    all_roles = (await db.execute(select(Role).where(Role.tenant_id == tenant_id))).scalars().all()
    role_map = {r.code: r.id for r in all_roles}

    all_depts = (await db.execute(select(Department).where(Department.tenant_id == tenant_id))).scalars().all()
    dept_map = {d.name: d.id for d in all_depts}

    success = 0
    failed = []
    created_ids: list[str] = []

    for i, row in enumerate(rows):
        try:
            username = (row.get("username") or "").strip()
            password = (row.get("password") or "").strip()
            real_name = (row.get("real_name") or "").strip()

            if not username or not password or not real_name:
                failed.append({"row": i + 2, "reason": "用户名、密码和姓名不能为空"})
                continue

            existing = (await db.execute(
                select(User).where(User.username == username, User.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if existing:
                failed.append({"row": i + 2, "reason": f"用户名 {username} 已存在"})
                continue

            role_ids = []
            for code in re.split(r'[;,]', row.get("role_codes") or ""):
                code = code.strip()
                if code and code in role_map:
                    role_ids.append(role_map[code])

            dept_ids = []
            for name in re.split(r'[;,]', row.get("department_names") or ""):
                name = name.strip()
                if name and name in dept_map:
                    dept_ids.append(dept_map[name])

            user = User(
                id=generate_uuid(), tenant_id=tenant_id,
                username=username,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                real_name=real_name,
                phone=(row.get("phone") or "").strip() or None,
                email=(row.get("email") or "").strip() or None,
            )
            db.add(user)
            for rid in role_ids:
                db.add(UserRole(id=generate_uuid(), tenant_id=tenant_id, user_id=user.id, role_id=rid))
            for did in dept_ids:
                db.add(UserDepartment(id=generate_uuid(), tenant_id=tenant_id, user_id=user.id, department_id=did))
            await db.flush()
            created_ids.append(user.id)
            success += 1
        except Exception as e:
            failed.append({"row": i + 2, "reason": str(e)})

    await db.commit()
    # 按「部门→角色」规则给导入的用户自动补角色(仅新增)
    if created_ids:
        from app.common.dept_role_auto import apply_dept_role_rules_bulk
        await apply_dept_role_rules_bulk(db, tenant_id, created_ids)
    return {"success": success, "failed": failed, "total": len(rows)}


async def reset_password(db: AsyncSession, tenant_id: str, user_id: str, new_password: str):
    user = (await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user:
        raise BusinessException(code=NOT_FOUND, message="用户不存在")
    user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    await db.commit()


# ==================== Role ====================

async def list_roles(db: AsyncSession, tenant_id: str):
    result = await db.execute(select(Role).where(Role.tenant_id == tenant_id).order_by(Role.created_at))
    return result.scalars().all()


async def create_role(db: AsyncSession, tenant_id: str, data: RoleCreate) -> Role:
    existing = (await db.execute(
        select(Role).where(Role.code == data.code, Role.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"角色编码 {data.code} 已存在")

    role = Role(id=generate_uuid(), tenant_id=tenant_id, code=data.code, name=data.name,
                description=data.description, data_scope=data.data_scope)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, tenant_id: str, role_id: str, data) -> Role:
    role = (await db.execute(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id))).scalar_one_or_none()
    if not role:
        raise BusinessException(code=NOT_FOUND, message="角色不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(role, field, val)
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, tenant_id: str, role_id: str):
    role = (await db.execute(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id))).scalar_one_or_none()
    if not role:
        raise BusinessException(code=NOT_FOUND, message="角色不存在")
    if role.is_system:
        raise BusinessException(message="系统角色不能删除")
    # Check if any users have this role
    user_count = (await db.execute(
        select(func.count(UserRole.id)).where(UserRole.role_id == role_id, UserRole.tenant_id == tenant_id)
    )).scalar() or 0
    if user_count > 0:
        raise BusinessException(message=f"该角色下有 {user_count} 个用户，请先移除用户再删除角色")
    # Delete role permissions
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id, RolePermission.tenant_id == tenant_id))
    # 清理引用该角色的「部门→角色」规则，避免外键冲突
    await db.execute(delete(DeptRoleRule).where(DeptRoleRule.role_id == role_id, DeptRoleRule.tenant_id == tenant_id))
    await db.delete(role)
    await db.commit()


async def grant_permissions(db: AsyncSession, tenant_id: str, role_id: str, permission_ids: list[str]):
    role = (await db.execute(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id))).scalar_one_or_none()
    if not role:
        raise BusinessException(code=NOT_FOUND, message="角色不存在")

    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id, RolePermission.tenant_id == tenant_id))
    for pid in permission_ids:
        db.add(RolePermission(id=generate_uuid(), tenant_id=tenant_id, role_id=role_id, permission_id=pid))

    await db.commit()
    # 角色权限变更会影响所有持有该角色的用户，失效整租户的权限缓存（issue #49）
    from app.domains.auth.service import invalidate_tenant_auth_cache
    await invalidate_tenant_auth_cache(tenant_id)


async def list_permissions(db: AsyncSession):
    result = await db.execute(select(Permission).order_by(Permission.group_name, Permission.code))
    return result.scalars().all()


# ==================== Dept -> Role auto-assignment rules ====================

async def list_dept_role_rules(db: AsyncSession, tenant_id: str) -> list[dict]:
    """列出本租户的部门→角色规则，附带部门/角色的展示名。"""
    rows = (await db.execute(
        select(DeptRoleRule, Department.name, Department.path, Role.code, Role.name)
        .outerjoin(Department, (Department.id == DeptRoleRule.department_id) & (Department.tenant_id == DeptRoleRule.tenant_id))
        .outerjoin(Role, (Role.id == DeptRoleRule.role_id) & (Role.tenant_id == DeptRoleRule.tenant_id))
        .where(DeptRoleRule.tenant_id == tenant_id)
        .order_by(Department.path)
    )).all()
    out = []
    for rule, dept_name, dept_path, role_code, role_name in rows:
        out.append({
            "id": rule.id,
            "department_id": rule.department_id,
            "department_name": dept_name,
            "department_path": dept_path,
            "role_id": rule.role_id,
            "role_code": role_code,
            "role_name": role_name,
            "include_children": rule.include_children,
            "enabled": rule.enabled,
        })
    return out


async def create_dept_role_rule(db: AsyncSession, tenant_id: str, data: DeptRoleRuleCreate) -> DeptRoleRule:
    # 校验部门/角色都属于本租户（防跨租户注入）
    await _validate_role_dept_ids(db, tenant_id, [data.role_id], [data.department_id])
    existing = (await db.execute(
        select(DeptRoleRule).where(
            DeptRoleRule.tenant_id == tenant_id,
            DeptRoleRule.department_id == data.department_id,
            DeptRoleRule.role_id == data.role_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=DUPLICATE_ENTRY, message="该部门与角色的规则已存在")
    rule = DeptRoleRule(
        id=generate_uuid(), tenant_id=tenant_id,
        department_id=data.department_id, role_id=data.role_id,
        include_children=data.include_children, enabled=data.enabled,
    )
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError:
        # 与并发创建撞上 uq_dept_role_rule 唯一键 —— 回滚并给出干净提示，而非 500
        await db.rollback()
        raise BusinessException(code=DUPLICATE_ENTRY, message="该部门与角色的规则已存在")
    await db.refresh(rule)
    return rule


async def update_dept_role_rule(db: AsyncSession, tenant_id: str, rule_id: str, data: DeptRoleRuleUpdate) -> DeptRoleRule:
    rule = (await db.execute(
        select(DeptRoleRule).where(DeptRoleRule.id == rule_id, DeptRoleRule.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rule:
        raise BusinessException(code=NOT_FOUND, message="规则不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, val)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_dept_role_rule(db: AsyncSession, tenant_id: str, rule_id: str):
    rule = (await db.execute(
        select(DeptRoleRule).where(DeptRoleRule.id == rule_id, DeptRoleRule.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rule:
        raise BusinessException(code=NOT_FOUND, message="规则不存在")
    await db.delete(rule)
    await db.commit()


async def apply_dept_role_rules_now(db: AsyncSession, tenant_id: str) -> dict:
    """把当前所有规则立即应用到本租户全部存量用户（仅新增角色）。"""
    from app.common.dept_role_auto import apply_dept_role_rules_bulk
    return await apply_dept_role_rules_bulk(db, tenant_id, None)
