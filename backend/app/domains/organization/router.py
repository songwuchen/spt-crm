from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.organization.schemas import (
    DepartmentCreate, DepartmentUpdate, DepartmentOut,
    UserCreate, UserUpdate, UserOut, ResetPassword,
    RoleCreate, RoleOut, GrantPermissions,
)
from app.domains.organization import service

router = APIRouter(prefix="/api/admin/v1/tenant", tags=["组织管理"])


# ---- Department ----
@router.get("/departments/tree")
async def dept_tree(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dept:view")),
):
    tree = await service.get_department_tree(db, tenant_id)
    return ok(tree)


@router.post("/departments")
async def create_dept(
    body: DepartmentCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dept:manage")),
):
    dept = await service.create_department(db, tenant_id, body)
    return ok(DepartmentOut.model_validate(dept).model_dump())


@router.put("/departments/{dept_id}")
async def update_dept(
    dept_id: str,
    body: DepartmentUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dept:manage")),
):
    dept = await service.update_department(db, tenant_id, dept_id, body)
    return ok(DepartmentOut.model_validate(dept).model_dump())


@router.delete("/departments/{dept_id}")
async def delete_dept(
    dept_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dept:manage")),
):
    await service.delete_department(db, tenant_id, dept_id)
    return ok()


# ---- User ----
@router.get("/users")
async def list_users(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:view")),
):
    items, total = await service.list_users(db, tenant_id, pageNo, pageSize, keyword)
    user_list = []
    for u in items:
        user_list.append({
            "id": u.id, "username": u.username, "real_name": u.real_name,
            "phone": u.phone, "email": u.email, "is_active": u.is_active,
            "roles": [ur.role.code for ur in u.user_roles],
            "departments": [ud.department.name for ud in u.user_departments],
        })
    return ok({"items": user_list, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/users")
async def create_user(
    body: UserCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:manage")),
):
    user = await service.create_user(db, tenant_id, body)
    return ok({"id": user.id, "username": user.username, "real_name": user.real_name})


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:manage")),
):
    user = await service.update_user(db, tenant_id, user_id, body)
    return ok({"id": user.id, "username": user.username, "real_name": user.real_name})


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:view")),
):
    u = await service.get_user(db, tenant_id, user_id)
    return ok({
        "id": u.id, "username": u.username, "real_name": u.real_name,
        "phone": u.phone, "email": u.email, "is_active": u.is_active,
        "roles": [ur.role.code for ur in u.user_roles],
        "departments": [ud.department.name for ud in u.user_departments],
    })


@router.post("/users/{user_id}/reset_password")
async def reset_password(
    user_id: str,
    body: ResetPassword,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:manage")),
):
    await service.reset_password(db, tenant_id, user_id, body.new_password)
    return ok()


# ---- Role ----
@router.get("/roles")
async def list_roles(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:view")),
):
    roles = await service.list_roles(db, tenant_id)
    role_list = []
    for r in roles:
        role_list.append({
            "id": r.id, "code": r.code, "name": r.name,
            "description": r.description, "is_system": r.is_system,
            "permissions": [rp.permission.code for rp in r.role_permissions],
        })
    return ok(role_list)


@router.post("/roles")
async def create_role(
    body: RoleCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    role = await service.create_role(db, tenant_id, body)
    return ok({"id": role.id, "code": role.code, "name": role.name})


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    await service.delete_role(db, tenant_id, role_id)
    return ok()


@router.post("/roles/{role_id}/grant_permissions")
async def grant_perms(
    role_id: str,
    body: GrantPermissions,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    await service.grant_permissions(db, tenant_id, role_id, body.permission_ids)
    return ok()


@router.get("/permissions")
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:view")),
):
    perms = await service.list_permissions(db)
    return ok([{"id": p.id, "code": p.code, "name": p.name, "group_name": p.group_name} for p in perms])
