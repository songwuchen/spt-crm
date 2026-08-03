from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.contract_review import service
from app.domains.contract_review.schemas import ContractReviewCreate, ContractReviewUpdate

router = APIRouter(prefix="/api/v1/contract-reviews", tags=["合同评审"])


def _to_dict(r) -> dict:
    return {
        "id": r.id,
        "review_code": r.review_code,
        "review_type": r.review_type,
        "status": r.status,
        "customer_id": r.customer_id,
        "company_name": r.company_name,
        "owner_id": r.owner_id,
        "owner_name": r.owner_name,
        "department_id": r.department_id,
        "department_name": r.department_name,
        "region_manager_id": r.region_manager_id,
        "region_manager_name": r.region_manager_name,
        "is_export": r.is_export,
        "need_pricing": r.need_pricing,
        "need_install": r.need_install,
        "customer_type": r.customer_type,
        "elec_ctrl": r.elec_ctrl,
        "project_title": r.project_title,
        "reported_at": r.reported_at.isoformat() if r.reported_at else None,
        "contract_amount": float(r.contract_amount) if r.contract_amount is not None else None,
        "delivery_period": r.delivery_period,
        "conclusion": r.conclusion,
        "payment_term": r.payment_term,
        "review_json": r.review_json or {},
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
    review_type: str | None = Query(None),
    keyword: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("contract_review:view")),
):
    items, total = await service.list_reviews(
        db, tenant_id, pageNo, pageSize, status, review_type, keyword, current_user=u,
    )
    return ok({
        "items": [_to_dict(r) for r in items],
        "total": total,
        "pageNo": pageNo,
        "pageSize": pageSize,
    })


@router.post("")
async def create_review(
    body: ContractReviewCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("contract_review:create")),
):
    return ok(_to_dict(await service.create_review(db, tenant_id, body, u)))


@router.get("/{rid}")
async def get_review(
    rid: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _u=Depends(require_permissions("contract_review:view")),
):
    return ok(_to_dict(await service.get_review(db, tenant_id, rid)))


@router.put("/{rid}")
async def update_review(
    rid: str,
    body: ContractReviewUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("contract_review:edit")),
):
    return ok(_to_dict(await service.update_review(db, tenant_id, rid, body, u)))


@router.delete("/{rid}")
async def delete_review(
    rid: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("contract_review:delete")),
):
    await service.delete_review(db, tenant_id, rid, u)
    return ok()


@router.post("/{rid}/submit")
async def submit_review(
    rid: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_permissions("contract_review:edit")),
):
    """提交合同评审审批（走流程管理 contract_review）。"""
    return ok(_to_dict(await service.submit_for_approval(db, tenant_id, rid, u)))
