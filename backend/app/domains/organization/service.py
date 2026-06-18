import re
import csv
import io
import bcrypt
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, DUPLICATE_ENTRY
from app.domains.organization.models import Department, UserDepartment
from app.domains.auth.models import User, Role, UserRole, RolePermission, Permission
from app.domains.organization.schemas import (
    DepartmentCreate, DepartmentUpdate, UserCreate, UserUpdate, RoleCreate, GrantPermissions,
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


async def list_users(db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20, keyword: str | None = None):
    base = select(User).where(User.tenant_id == tenant_id)
    if keyword:
        base = base.where(User.real_name.ilike(f"%{keyword}%") | User.username.ilike(f"%{keyword}%"))

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

    if department_ids is not None:
        await db.execute(delete(UserDepartment).where(UserDepartment.user_id == user_id, UserDepartment.tenant_id == tenant_id))
        for did in department_ids:
            db.add(UserDepartment(id=generate_uuid(), tenant_id=tenant_id, user_id=user_id, department_id=did))

    await db.commit()
    await db.refresh(user)
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
    return len(valid_ids)


async def delete_user(db: AsyncSession, tenant_id: str, user_id: str, current_user_id: str):
    user = (await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user:
        raise BusinessException(code=NOT_FOUND, message="用户不存在")
    if user_id == current_user_id:
        raise BusinessException(message="不能删除当前登录用户")
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id))
    await db.execute(delete(UserDepartment).where(UserDepartment.user_id == user_id, UserDepartment.tenant_id == tenant_id))
    await db.delete(user)
    await db.commit()


async def import_users(db: AsyncSession, tenant_id: str, rows: list) -> dict:
    all_roles = (await db.execute(select(Role).where(Role.tenant_id == tenant_id))).scalars().all()
    role_map = {r.code: r.id for r in all_roles}

    all_depts = (await db.execute(select(Department).where(Department.tenant_id == tenant_id))).scalars().all()
    dept_map = {d.name: d.id for d in all_depts}

    success = 0
    failed = []

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
            success += 1
        except Exception as e:
            failed.append({"row": i + 2, "reason": str(e)})

    await db.commit()
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


async def list_permissions(db: AsyncSession):
    result = await db.execute(select(Permission).order_by(Permission.group_name, Permission.code))
    return result.scalars().all()
