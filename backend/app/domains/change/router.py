from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.change import service
from app.domains.change.models import ChangeRequest
from app.domains.change.schemas import ChangeRequestCreate, ChangeRequestUpdate

router = APIRouter(tags=["变更管理"])


def _cr_dict(c) -> dict:
    return {
        "id": c.id, "project_id": c.project_id,
        "change_no": c.change_no, "change_type": c.change_type,
        "from_version_ref_json": c.from_version_ref_json,
        "to_version_ref_json": c.to_version_ref_json,
        "reason": c.reason, "impact_json": c.impact_json,
        "status": c.status,
        "created_by_id": c.created_by_id, "created_by_name": c.created_by_name,
        "assignee_id": c.assignee_id, "assignee_name": c.assignee_name,
        "department_id": c.department_id, "department_name": c.department_name,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


@router.get("/api/v1/change_requests")
async def list_all_change_requests(
    page_no: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    change_type: str | None = None,
    keyword: str | None = None,
    filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str = Query(None),
    sort_order: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("change:view")),
):
    """Global list of all change requests with pagination and filters."""
    q = select(ChangeRequest).where(ChangeRequest.tenant_id == tenant_id)
    cq = select(func.count()).select_from(ChangeRequest).where(ChangeRequest.tenant_id == tenant_id)
    if status:
        q = q.where(ChangeRequest.status == status)
        cq = cq.where(ChangeRequest.status == status)
    if change_type:
        q = q.where(ChangeRequest.change_type == change_type)
        cq = cq.where(ChangeRequest.change_type == change_type)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(ChangeRequest.change_no.ilike(like) | ChangeRequest.reason.ilike(like))
        cq = cq.where(ChangeRequest.change_no.ilike(like) | ChangeRequest.reason.ilike(like))
    # 高级筛选（多字段/多条件）
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("change", filter, {"user_id": current_user.get("sub")})
    if clause is not None:
        q = q.where(clause)
        cq = cq.where(clause)
    from app.common.data_scope import apply_project_child_scope
    q, cq = await apply_project_child_scope(q, cq, db, tenant_id, current_user, ChangeRequest)
    total = (await db.execute(cq)).scalar() or 0
    order = resolve_sort("change", sort_by, sort_order) or ChangeRequest.created_at.desc()
    q = q.order_by(order).offset((page_no - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()
    return ok({"items": [_cr_dict(c) for c in items], "total": total})


@router.get("/api/v1/projects/{project_id}/change_requests")
async def list_change_requests(
    project_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("change:view")),
):
    items = await service.list_by_project(db, tenant_id, project_id)
    return ok([_cr_dict(c) for c in items])


@router.post("/api/v1/projects/{project_id}/change_requests")
async def create_change_request(
    project_id: str, body: ChangeRequestCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("change:create")),
):
    cr = await service.create(db, tenant_id, project_id, body, current_user)
    return ok(_cr_dict(cr))


@router.get("/api/v1/change_requests/{cr_id}")
async def get_change_request(
    cr_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("change:view")),
):
    cr = await service.get(db, tenant_id, cr_id)
    return ok(_cr_dict(cr))


@router.put("/api/v1/change_requests/{cr_id}")
async def update_change_request(
    cr_id: str, body: ChangeRequestUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("change:edit")),
):
    cr = await service.update(db, tenant_id, cr_id, body, current_user)
    return ok(_cr_dict(cr))


@router.post("/api/v1/change_requests/{cr_id}/estimate_impact")
async def estimate_impact(
    cr_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("change:edit")),
):
    impact = await service.estimate_impact(db, tenant_id, cr_id, current_user)
    return ok(impact)


@router.delete("/api/v1/change_requests/{cr_id}")
async def delete_change_request(
    cr_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), current_user: dict = Depends(require_permissions("change:delete")),
):
    await service.delete(db, tenant_id, cr_id, current_user)
    return ok(None)
