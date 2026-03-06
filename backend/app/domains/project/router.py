from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions, get_data_scope
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.project import service
from app.domains.project.schemas import ProjectCreate, ProjectUpdate, StageAdvance, StageRollback

router = APIRouter(prefix="/api/v1/projects", tags=["商机项目"])


def _project_dict(p) -> dict:
    return {
        "id": p.id, "project_code": p.project_code,
        "customer_id": p.customer_id, "name": p.name,
        "stage_code": p.stage_code,
        "amount_expect": float(p.amount_expect) if p.amount_expect is not None else None,
        "probability": p.probability,
        "close_date_expect": str(p.close_date_expect) if p.close_date_expect else None,
        "competitors_json": p.competitors_json,
        "key_requirements_json": p.key_requirements_json,
        "risk_level": p.risk_level,
        "owner_id": p.owner_id, "owner_name": p.owner_name,
        "status": p.status, "remark": p.remark,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


def _history_dict(h) -> dict:
    return {
        "id": h.id, "project_id": h.project_id,
        "from_stage": h.from_stage, "to_stage": h.to_stage,
        "changed_by_id": h.changed_by_id, "changed_by_name": h.changed_by_name,
        "note": h.note,
        "created_at": h.created_at.isoformat() if h.created_at else "",
    }


@router.get("")
async def list_projects(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    stage_code: str = Query(None),
    customer_id: str = Query(None),
    status: str = Query(None),
    owner_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
    data_scope: str | None = Depends(get_data_scope),
):
    effective_owner = owner_id or data_scope
    items, total = await service.list_projects(db, tenant_id, pageNo, pageSize, keyword, stage_code, customer_id, status, effective_owner)
    return ok({"items": [_project_dict(p) for p in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/export/excel")
async def export_projects_excel(
    keyword: str = Query(None),
    stage_code: str = Query(None),
    customer_id: str = Query(None),
    status: str = Query(None),
    owner_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items, _ = await service.list_projects(db, tenant_id, 1, 5000, keyword, stage_code, customer_id, status, owner_id)
    headers = ["项目编码", "项目名称", "阶段", "预计金额", "概率(%)", "预计关闭日", "风险等级", "负责人", "状态", "创建时间"]
    rows = []
    for p in items:
        rows.append([
            p.project_code, p.name or "", p.stage_code or "",
            float(p.amount_expect) if p.amount_expect is not None else "",
            p.probability or "", str(p.close_date_expect) if p.close_date_expect else "",
            p.risk_level or "", p.owner_name or "", p.status or "",
            p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
        ])
    buf = build_excel("商机项目", headers, rows)
    return excel_response(buf, "projects.xlsx")


@router.post("")
async def create_project(
    body: ProjectCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:create")),
):
    p = await service.create_project(db, tenant_id, body, current_user)
    return ok(_project_dict(p))


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    p = await service.get_project(db, tenant_id, project_id)
    return ok(_project_dict(p))


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    p = await service.update_project(db, tenant_id, project_id, body, current_user)
    return ok(_project_dict(p))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:delete")),
):
    await service.delete_project(db, tenant_id, project_id, current_user)
    return ok()


@router.post("/{project_id}/advance")
async def advance_stage(
    project_id: str,
    body: StageAdvance,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:advance")),
):
    p = await service.advance_stage(db, tenant_id, project_id, body.to_stage, body.note, current_user, force=body.force or False)
    return ok(_project_dict(p))


@router.post("/{project_id}/rollback")
async def rollback_stage(
    project_id: str,
    body: StageRollback,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:advance")),
):
    p = await service.rollback_stage(db, tenant_id, project_id, body.to_stage, body.note, current_user)
    return ok(_project_dict(p))


@router.get("/{project_id}/gate_check")
async def gate_check(
    project_id: str,
    to_stage: str = Query(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    project = await service.get_project(db, tenant_id, project_id)
    failed = await service.check_gate_rules(db, tenant_id, project, to_stage)
    return ok({"pass": len(failed) == 0, "failed_rules": failed})


@router.get("/{project_id}/health")
async def project_health(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    result = await service.calculate_health_score(db, tenant_id, project_id)
    return ok(result)


@router.get("/{project_id}/stage_history")
async def list_stage_history(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items = await service.list_stage_history(db, tenant_id, project_id)
    return ok([_history_dict(h) for h in items])


# ---- ACL Shares (project-level) ----
@router.get("/{project_id}/shares")
async def list_project_shares(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    from app.domains.customer.service import list_shares
    items = await list_shares(db, tenant_id, "project", project_id)
    return ok([{
        "id": s.id, "biz_type": s.biz_type, "biz_id": s.biz_id,
        "shared_to_type": s.shared_to_type, "shared_to_id": s.shared_to_id,
        "shared_to_name": s.shared_to_name, "permission": s.permission,
        "shared_by_name": s.shared_by_name,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    } for s in items])


@router.post("/{project_id}/shares")
async def create_project_share(
    project_id: str,
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    from app.domains.customer.service import create_share
    body["biz_type"] = "project"
    body["biz_id"] = project_id
    s = await create_share(db, tenant_id, body, current_user)
    return ok({"id": s.id, "shared_to_name": s.shared_to_name})


@router.delete("/{project_id}/shares/{share_id}")
async def delete_project_share(
    project_id: str,
    share_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    from app.domains.customer.service import delete_share
    await delete_share(db, tenant_id, share_id, current_user)
    return ok()
