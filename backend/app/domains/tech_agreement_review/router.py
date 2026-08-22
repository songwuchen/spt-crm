from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.tech_agreement_review import service
from app.domains.tech_agreement_review.schemas import (
    TechAgreementReviewCreate, TechAgreementReviewUpdate,
)

router = APIRouter(prefix="/api/v1/tech-agreement-reviews", tags=["技术协议评审"])


def _to_dict(r) -> dict:
    return {
        "id": r.id,
        "review_code": r.review_code,
        "status": r.status,
        "customer_id": r.customer_id,
        "company_name": r.company_name,
        "applicant_id": r.applicant_id,
        "applicant_name": r.applicant_name,
        "apply_at": r.apply_at.isoformat() if r.apply_at else None,
        "owner_id": r.owner_id,
        "owner_name": r.owner_name,
        "department_id": r.department_id,
        "department_name": r.department_name,
        "industry": r.industry,
        "address": r.address,
        "elec_ctrl": r.elec_ctrl,
        "project_title": r.project_title,
        "has_weight_req": r.has_weight_req,
        "use_idle_equip": r.use_idle_equip,
        "has_smart": r.has_smart,
        "need_pricing": r.need_pricing,
        "sign_basis": r.sign_basis,
        "ref_contract_no": r.ref_contract_no,
        "pre_contact": r.pre_contact,
        "remark": r.remark,
        "has_objection": r.has_objection,
        "form_json": r.form_json or {},
        "created_by_id": r.created_by_id,
        "created_by_name": r.created_by_name,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


@router.get("")
async def list_reviews(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    created_by_id: str | None = Query(None, description="提交人用户 ID"),
    filter: str | None = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str | None = Query(None),
    sort_order: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("tech_agreement_review:view")),
):
    items, total = await service.list_reviews(
        db, tenant_id, pageNo, pageSize, status, keyword,
        created_by_id=created_by_id,
        current_user=u, filter=filter, sort_by=sort_by, sort_order=sort_order,
    )
    return ok({
        "items": [_to_dict(r) for r in items],
        "total": total,
        "pageNo": pageNo,
        "pageSize": pageSize,
    })


@router.post("")
async def create_review(
    body: TechAgreementReviewCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("tech_agreement_review:create")),
):
    return ok(_to_dict(await service.create_review(db, tenant_id, body, u)))


@router.get("/{rid}")
async def get_review(
    rid: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _u=Depends(require_permissions("tech_agreement_review:view")),
):
    return ok(_to_dict(await service.get_review(db, tenant_id, rid)))


@router.put("/{rid}")
async def update_review(
    rid: str,
    body: TechAgreementReviewUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("tech_agreement_review:edit")),
):
    return ok(_to_dict(await service.update_review(db, tenant_id, rid, body, u)))


@router.delete("/{rid}")
async def delete_review(
    rid: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("tech_agreement_review:delete")),
):
    await service.delete_review(db, tenant_id, rid, u)
    return ok()


@router.post("/{rid}/submit")
async def submit_review(
    rid: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("tech_agreement_review:edit")),
):
    """提交技术协议评审审批。"""
    return ok(_to_dict(await service.submit_for_approval(db, tenant_id, rid, u)))
