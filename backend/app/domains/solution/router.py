from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.solution import service
from app.domains.solution.schemas import SolutionCreate, SolutionUpdate, SolutionVersionUpdate

router = APIRouter(tags=["方案管理"])


def _solution_dict(s) -> dict:
    return {
        "id": s.id, "project_id": s.project_id, "solution_no": s.solution_no,
        "current_version_no": s.current_version_no, "status": s.status,
        "created_by_id": s.created_by_id, "created_by_name": s.created_by_name,
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
    }


def _version_dict(v) -> dict:
    return {
        "id": v.id, "solution_id": v.solution_id, "version_no": v.version_no,
        "title": v.title, "summary": v.summary,
        "config_json": v.config_json, "risk_list_json": v.risk_list_json,
        "ai_insights_json": v.ai_insights_json,
        "doc_attachment_id": v.doc_attachment_id,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else "",
    }


# --- Project-scoped routes ---

@router.get("/api/v1/projects/{project_id}/solutions")
async def list_project_solutions(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("solution:view")),
):
    items = await service.list_solutions_by_project(db, tenant_id, project_id)
    return ok([_solution_dict(s) for s in items])


@router.post("/api/v1/projects/{project_id}/solutions")
async def create_solution(
    project_id: str,
    body: SolutionCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("solution:create")),
):
    result = await service.create_solution(db, tenant_id, project_id, body, current_user)
    return ok({
        "solution": _solution_dict(result["solution"]),
        "version": _version_dict(result["version"]),
    })


# --- Solution routes ---

@router.get("/api/v1/solutions/{solution_id}")
async def get_solution(
    solution_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("solution:view")),
):
    solution = await service.get_solution(db, tenant_id, solution_id)
    versions = await service.get_versions_by_solution(db, tenant_id, solution_id)
    current_ver = next((v for v in versions if v.version_no == solution.current_version_no), None)

    return ok({
        **_solution_dict(solution),
        "versions": [_version_dict(v) for v in versions],
        "current_version": _version_dict(current_ver) if current_ver else None,
    })


@router.put("/api/v1/solutions/{solution_id}")
async def update_solution(
    solution_id: str,
    body: SolutionUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("solution:edit")),
):
    s = await service.update_solution(db, tenant_id, solution_id, body, current_user)
    return ok(_solution_dict(s))


@router.delete("/api/v1/solutions/{solution_id}")
async def delete_solution(
    solution_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("solution:delete")),
):
    await service.delete_solution(db, tenant_id, solution_id, current_user)
    return ok(None)


@router.post("/api/v1/solutions/{solution_id}/new_version")
async def new_version(
    solution_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("solution:edit")),
):
    v = await service.new_version(db, tenant_id, solution_id, current_user)
    return ok(_version_dict(v))


# --- Version routes ---

@router.get("/api/v1/solution_versions/{version_id}")
async def get_version(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("solution:view")),
):
    v = await service.get_version(db, tenant_id, version_id)
    return ok(_version_dict(v))


@router.put("/api/v1/solution_versions/{version_id}")
async def update_version(
    version_id: str,
    body: SolutionVersionUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("solution:edit")),
):
    v = await service.update_version(db, tenant_id, version_id, body, current_user)
    return ok(_version_dict(v))
