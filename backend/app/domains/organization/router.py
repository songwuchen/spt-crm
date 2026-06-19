import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.domains.admin.models import IntegrationEndpoint
from app.database import generate_uuid
from app.domains.organization.schemas import (
    DepartmentCreate, DepartmentUpdate, DepartmentOut,
    UserCreate, UserUpdate, UserBulkRoles, UserOut, ResetPassword,
    RoleCreate, RoleUpdate, RoleOut, GrantPermissions,
)
from app.domains.organization import service


class DingTalkConfigBody(BaseModel):
    app_key: str
    app_secret: str
    default_password: Optional[str] = "Changeme@123"
    root_dept_id: Optional[int] = 1
    login_enabled: Optional[bool] = False

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


@router.post("/users/bulk_roles")
async def bulk_set_user_roles(
    body: UserBulkRoles,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:manage")),
):
    n = await service.bulk_set_roles(db, tenant_id, body.user_ids, body.role_ids, body.mode)
    return ok({"updated": n})


@router.post("/users")
async def create_user(
    body: UserCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:manage")),
):
    user = await service.create_user(db, tenant_id, body)
    return ok({"id": user.id, "username": user.username, "real_name": user.real_name})


@router.get("/users/export")
async def export_users(
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:view")),
):
    items, _ = await service.list_users(db, tenant_id, 1, 10000, keyword)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["username", "real_name", "phone", "email", "role_codes", "department_names", "status"])
    for u in items:
        writer.writerow([
            u.username,
            u.real_name,
            u.phone or "",
            u.email or "",
            ",".join(ur.role.code for ur in u.user_roles),
            ",".join(ud.department.name for ud in u.user_departments),
            "active" if u.is_active else "inactive",
        ])
    content = "\ufeff" + buf.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@router.post("/users/import")
async def import_users(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("user:manage")),
):
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    result = await service.import_users(db, tenant_id, rows)
    return ok(result)


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


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("user:manage")),
):
    await service.delete_user(db, tenant_id, user_id, current_user["sub"])
    return ok()


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
            "data_scope": r.data_scope or "self",
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


@router.put("/roles/{role_id}")
async def update_role(
    role_id: str,
    body: RoleUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    role = await service.update_role(db, tenant_id, role_id, body)
    return ok({"id": role.id, "code": role.code, "name": role.name, "data_scope": role.data_scope})


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


# ==================== DingTalk OA Integration ====================

_DT_OA_CODE = "dingtalk_oa"


async def _get_dt_endpoint(db: AsyncSession, tenant_id: str) -> Optional[IntegrationEndpoint]:
    return (await db.execute(
        select(IntegrationEndpoint).where(
            IntegrationEndpoint.tenant_id == tenant_id,
            IntegrationEndpoint.system_code == _DT_OA_CODE,
        )
    )).scalar_one_or_none()


@router.get("/dingtalk/config")
async def get_dingtalk_config(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    ep = await _get_dt_endpoint(db, tenant_id)
    if not ep:
        return ok(None)
    cfg = ep.auth_config_json or {}
    return ok({
        "app_key": cfg.get("app_key", ""),
        "app_secret": "******" if cfg.get("app_secret") else "",
        "default_password": cfg.get("default_password", "Changeme@123"),
        "root_dept_id": cfg.get("root_dept_id", 1),
        "login_enabled": cfg.get("login_enabled", False),
        "status": ep.status,
    })


@router.post("/dingtalk/config")
async def save_dingtalk_config(
    body: DingTalkConfigBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    ep = await _get_dt_endpoint(db, tenant_id)
    cfg = {
        "app_key": body.app_key,
        "app_secret": body.app_secret,
        "default_password": body.default_password or "Changeme@123",
        "root_dept_id": body.root_dept_id or 1,
        "login_enabled": body.login_enabled or False,
    }
    from app.common.crypto import encrypt_config_json
    if ep:
        # preserve existing secret if masked value sent (stored value may be enc:…)
        if body.app_secret == "******":
            cfg["app_secret"] = (ep.auth_config_json or {}).get("app_secret", "")
        ep.auth_config_json = encrypt_config_json(cfg)
        ep.status = "active"
    else:
        ep = IntegrationEndpoint(
            id=generate_uuid(), tenant_id=tenant_id,
            system_code=_DT_OA_CODE, name="钉钉组织架构同步",
            base_url="", auth_type="appkey",
            auth_config_json=encrypt_config_json(cfg), status="active",
        )
        db.add(ep)
    await db.commit()
    return ok({"saved": True})


@router.post("/dingtalk/test")
async def test_dingtalk(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    from app.common.dingtalk_sync import get_access_token, fetch_all_departments
    from app.common.crypto import decrypt_config_json
    ep = await _get_dt_endpoint(db, tenant_id)
    if not ep:
        raise BusinessException(message="请先配置钉钉参数")
    cfg = decrypt_config_json(ep.auth_config_json or {}) or {}
    app_key = cfg.get("app_key", "")
    app_secret = cfg.get("app_secret", "")
    if not app_key or not app_secret:
        raise BusinessException(message="AppKey 或 AppSecret 未配置")
    try:
        token = await get_access_token(app_key, app_secret)
        depts = await fetch_all_departments(token)
        return ok({"connected": True, "dept_count": len(depts)})
    except Exception as e:
        return ok({"connected": False, "error": str(e)})


async def _run_sync_departments_bg(task_id: str, tenant_id: str, cfg: dict, sync_leaders: bool) -> None:
    """Background runner: owns its own DB session; reports progress via sync_tasks store."""
    from app.common.dingtalk_sync import get_access_token, sync_departments
    from app.common import sync_tasks
    from app.database import async_session_factory

    async def _cb(phase: str, processed: int, total: int) -> None:
        await sync_tasks.update_progress(task_id, phase, processed, total)

    try:
        token = await get_access_token(cfg["app_key"], cfg["app_secret"])
        async with async_session_factory() as bg_db:
            result = await sync_departments(
                bg_db, tenant_id, token,
                sync_leaders=sync_leaders,
                progress_cb=_cb,
            )
        await sync_tasks.finish_task(task_id, result)
    except Exception as e:
        await sync_tasks.fail_task(task_id, f"同步部门失败: {e}")


async def _run_sync_users_bg(task_id: str, tenant_id: str, cfg: dict) -> None:
    from app.common.dingtalk_sync import get_access_token, sync_users
    from app.common import sync_tasks
    from app.database import async_session_factory

    async def _cb(phase: str, processed: int, total: int) -> None:
        await sync_tasks.update_progress(task_id, phase, processed, total)

    try:
        token = await get_access_token(cfg["app_key"], cfg["app_secret"])
        async with async_session_factory() as bg_db:
            result = await sync_users(
                bg_db, tenant_id, token,
                default_password=cfg.get("default_password", "Changeme@123"),
                progress_cb=_cb,
            )
        await sync_tasks.finish_task(task_id, result)
    except Exception as e:
        await sync_tasks.fail_task(task_id, f"同步用户失败: {e}")


@router.post("/dingtalk/sync/departments")
async def dingtalk_sync_departments(
    sync_leaders: bool = Query(True),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """Kick off department sync in background; returns task_id for status polling."""
    import asyncio
    from app.common import sync_tasks

    from app.common.crypto import decrypt_config_json
    ep = await _get_dt_endpoint(db, tenant_id)
    if not ep:
        raise BusinessException(message="请先配置钉钉参数")
    cfg = decrypt_config_json(ep.auth_config_json or {}) or {}

    # If a sync is already running for this tenant, reuse it so double-clicks don't double-fetch
    existing = sync_tasks.get_active_for_tenant(tenant_id, kind="dingtalk_departments")
    if existing:
        return ok({"task_id": existing, "reused": True})

    task_id = await sync_tasks.create_task(tenant_id, "dingtalk_departments")
    asyncio.create_task(_run_sync_departments_bg(task_id, tenant_id, cfg, sync_leaders))
    return ok({"task_id": task_id, "reused": False})


@router.post("/dingtalk/sync/users")
async def dingtalk_sync_users(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """Kick off user sync in background; returns task_id for status polling."""
    import asyncio
    from app.common import sync_tasks

    from app.common.crypto import decrypt_config_json
    ep = await _get_dt_endpoint(db, tenant_id)
    if not ep:
        raise BusinessException(message="请先配置钉钉参数")
    cfg = decrypt_config_json(ep.auth_config_json or {}) or {}

    existing = sync_tasks.get_active_for_tenant(tenant_id, kind="dingtalk_users")
    if existing:
        return ok({"task_id": existing, "reused": True})

    task_id = await sync_tasks.create_task(tenant_id, "dingtalk_users")
    asyncio.create_task(_run_sync_users_bg(task_id, tenant_id, cfg))
    return ok({"task_id": task_id, "reused": False})


@router.get("/dingtalk/sync/tasks/{task_id}")
async def dingtalk_sync_task_status(
    task_id: str,
    tenant_id: str = Depends(get_tenant_id),
    _user=Depends(require_permissions("role:manage")),
):
    from app.common import sync_tasks

    t = sync_tasks.get_task(task_id)
    if not t:
        raise BusinessException(code=40400, message="同步任务不存在或已过期")
    # Don't leak other tenants' tasks
    if t.get("tenant_id") != tenant_id:
        raise BusinessException(code=40300, message="无权访问此任务")
    return ok({
        "id": t["id"],
        "kind": t["kind"],
        "status": t["status"],
        "phase": t["phase"],
        "processed": t["processed"],
        "total": t["total"],
        "result": t["result"],
        "error": t["error"],
        "started_at": t["started_at"],
        "finished_at": t["finished_at"],
    })


@router.get("/dingtalk/sync/active")
async def dingtalk_sync_active(
    kind: Optional[str] = Query(None, pattern="^(dingtalk_departments|dingtalk_users)$"),
    tenant_id: str = Depends(get_tenant_id),
    _user=Depends(require_permissions("role:manage")),
):
    """Return the task_id of any running sync for this tenant — lets UI resume after refresh."""
    from app.common import sync_tasks

    return ok({"task_id": sync_tasks.get_active_for_tenant(tenant_id, kind=kind)})
