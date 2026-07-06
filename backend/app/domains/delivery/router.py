from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.delivery import service
from app.domains.delivery.models import DeliveryMilestone
from app.domains.delivery.schemas import ErpOrderLinkCreate, MilestoneCreate, MilestoneUpdate

router = APIRouter(tags=["交付管理"])


def _link_dict(l) -> dict:
    return {
        "id": l.id, "project_id": l.project_id,
        "erp_system_code": l.erp_system_code, "erp_order_no": l.erp_order_no,
        "sync_status": l.sync_status, "remark": l.remark,
        "created_at": l.created_at.isoformat() if l.created_at else "",
    }


def _ms_dict(m, attachment_count: int = 0) -> dict:
    return {
        "id": m.id, "project_id": m.project_id,
        "milestone_code": m.milestone_code, "name": m.name,
        "plan_date": str(m.plan_date) if m.plan_date else None,
        "actual_date": str(m.actual_date) if m.actual_date else None,
        "status": m.status, "source_type": m.source_type,
        "sort_order": m.sort_order, "note": m.note,
        "assignee_id": m.assignee_id, "assignee_name": m.assignee_name,
        "department_id": m.department_id, "department_name": m.department_name,
        "attachment_count": attachment_count,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    }


async def _ms_attachment_counts(db: AsyncSession, tenant_id: str, ids: list[str]) -> dict:
    """里程碑id -> 附件数。让附件在列表上可见(不必进编辑弹窗才知道有附件，issue #63)。"""
    if not ids:
        return {}
    from app.domains.attachment.models import AttachmentLink
    rows = (await db.execute(
        select(AttachmentLink.biz_id, func.count()).where(
            AttachmentLink.tenant_id == tenant_id,
            AttachmentLink.biz_type == "delivery_milestone",
            AttachmentLink.biz_id.in_(ids),
        ).group_by(AttachmentLink.biz_id)
    )).all()
    return {bid: cnt for bid, cnt in rows}


# --- ERP Order Links ---

@router.get("/api/v1/projects/{project_id}/order_links")
async def list_order_links(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("delivery:view")),
):
    items = await service.list_order_links(db, tenant_id, project_id)
    return ok([_link_dict(l) for l in items])


@router.post("/api/v1/projects/{project_id}/order_links")
async def create_order_link(
    project_id: str,
    body: ErpOrderLinkCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("delivery:edit")),
):
    link = await service.create_order_link(db, tenant_id, project_id, body, current_user)
    return ok(_link_dict(link))


@router.delete("/api/v1/order_links/{link_id}")
async def delete_order_link(
    link_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("delivery:edit")),
):
    await service.delete_order_link(db, tenant_id, link_id, current_user)
    return ok(None)


# --- Delivery Milestones ---

@router.get("/api/v1/milestones")
async def list_all_milestones(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str | None = None,
    keyword: str | None = None,
    filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str = Query(None),
    sort_order: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("delivery:view")),
):
    """Global list of all delivery milestones with pagination."""
    q = select(DeliveryMilestone).where(DeliveryMilestone.tenant_id == tenant_id)
    cq = select(func.count()).select_from(DeliveryMilestone).where(DeliveryMilestone.tenant_id == tenant_id)
    if status:
        q = q.where(DeliveryMilestone.status == status)
        cq = cq.where(DeliveryMilestone.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(DeliveryMilestone.name.ilike(like) | DeliveryMilestone.milestone_code.ilike(like))
        cq = cq.where(DeliveryMilestone.name.ilike(like) | DeliveryMilestone.milestone_code.ilike(like))
    # 高级筛选（多字段/多条件）
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("milestone", filter, {"user_id": current_user.get("sub")})
    if clause is not None:
        q = q.where(clause)
        cq = cq.where(clause)
    from app.common.data_scope import apply_project_child_scope
    q, cq = await apply_project_child_scope(q, cq, db, tenant_id, current_user, DeliveryMilestone)
    total = (await db.execute(cq)).scalar() or 0
    order = resolve_sort("milestone", sort_by, sort_order, DeliveryMilestone.created_at.desc())
    q = q.order_by(order).offset((pageNo - 1) * pageSize).limit(pageSize)
    items = (await db.execute(q)).scalars().all()
    counts = await _ms_attachment_counts(db, tenant_id, [m.id for m in items])
    from app.common.list_enrich import project_names_map
    name_map = await project_names_map(db, tenant_id, [m.project_id for m in items])
    return ok({"items": [{**_ms_dict(m, counts.get(m.id, 0)), **(name_map.get(m.project_id) or {})} for m in items], "total": total})


@router.get("/api/v1/projects/{project_id}/milestones")
async def list_milestones(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("delivery:view")),
):
    items = await service.list_milestones(db, tenant_id, project_id)
    counts = await _ms_attachment_counts(db, tenant_id, [m.id for m in items])
    return ok([_ms_dict(m, counts.get(m.id, 0)) for m in items])


@router.post("/api/v1/projects/{project_id}/milestones")
async def create_milestone(
    project_id: str,
    body: MilestoneCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("delivery:edit")),
):
    ms = await service.create_milestone(db, tenant_id, project_id, body, current_user)
    return ok(_ms_dict(ms))


@router.get("/api/v1/milestones/{milestone_id}")
async def get_milestone(
    milestone_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("delivery:view")),
):
    ms = await service.get_milestone(db, tenant_id, milestone_id)
    return ok(_ms_dict(ms))


@router.put("/api/v1/milestones/{milestone_id}")
async def update_milestone(
    milestone_id: str,
    body: MilestoneUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("delivery:edit")),
):
    ms = await service.update_milestone(db, tenant_id, milestone_id, body, current_user)
    return ok(_ms_dict(ms))


@router.delete("/api/v1/milestones/{milestone_id}")
async def delete_milestone(
    milestone_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("delivery:delete")),
):
    await service.delete_milestone(db, tenant_id, milestone_id, current_user)
    return ok(None)
