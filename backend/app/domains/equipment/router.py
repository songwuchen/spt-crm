from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.equipment import service
from app.domains.equipment.schemas import (
    EquipmentCreate, EquipmentUpdate, EquipmentToRenewal, SurveyCreate, SurveyUpdate,
)

router = APIRouter(prefix="/api/v1/equipment", tags=["客户工艺设备档案"])


def _eq_dict(e) -> dict:
    return {
        "id": e.id, "customer_id": e.customer_id, "customer_name": e.customer_name,
        "name": e.name, "category": e.category, "spec": e.spec, "supplier": e.supplier,
        "is_competitor": e.is_competitor,
        "usage_years": float(e.usage_years) if e.usage_years is not None else None,
        "quantity": e.quantity, "condition": e.condition,
        "replace_plan_date": str(e.replace_plan_date) if e.replace_plan_date else None,
        "spare_usage": e.spare_usage, "remark": e.remark,
        "created_by_name": e.created_by_name,
        "created_at": e.created_at.isoformat() if e.created_at else "",
    }


def _survey_dict(s) -> dict:
    return {
        "id": s.id, "customer_id": s.customer_id, "customer_name": s.customer_name,
        "industry": s.industry, "main_products": s.main_products, "annual_output": s.annual_output,
        "branch_info": s.branch_info, "process_desc": s.process_desc, "pain_points": s.pain_points,
        "survey_date": str(s.survey_date) if s.survey_date else None,
        "owner_id": s.owner_id, "owner_name": s.owner_name, "remark": s.remark,
        "created_by_name": s.created_by_name,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


# ---------- Equipment ----------
@router.get("/replacement-candidates")
async def replacement_candidates(months: int = Query(12, ge=1, le=60), tenant_id: str = Depends(get_tenant_id),
                                 db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("customer:view"))):
    rows = await service.replacement_candidates(db, tenant_id, months)
    return ok([_eq_dict(e) for e in rows])


@router.get("/equipments")
async def list_equipment(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                         customer_id: str = Query(None), is_competitor: bool = Query(None), keyword: str = Query(None),
                         tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                         _u=Depends(require_permissions("customer:view"))):
    items, total = await service.list_equipment(db, tenant_id, pageNo, pageSize, customer_id, is_competitor, keyword)
    return ok({"items": [_eq_dict(e) for e in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/equipments")
async def create_equipment(body: EquipmentCreate, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("customer:edit"))):
    return ok(_eq_dict(await service.create_equipment(db, tenant_id, body, u)))


@router.put("/equipments/{eid}")
async def update_equipment(eid: str, body: EquipmentUpdate, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("customer:edit"))):
    return ok(_eq_dict(await service.update_equipment(db, tenant_id, eid, body, u)))


@router.delete("/equipments/{eid}")
async def delete_equipment(eid: str, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("customer:edit"))):
    await service.delete_equipment(db, tenant_id, eid, u)
    return ok()


@router.post("/equipments/{eid}/to-renewal")
async def to_renewal(eid: str, body: EquipmentToRenewal, tenant_id: str = Depends(get_tenant_id),
                     db: AsyncSession = Depends(get_db), u=Depends(require_permissions("service:edit"))):
    r = await service.convert_to_renewal(db, tenant_id, eid, body, u)
    return ok({"id": r.id, "name": r.name})


# ---------- Surveys ----------
@router.get("/surveys")
async def list_surveys(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                       customer_id: str = Query(None), industry: str = Query(None), keyword: str = Query(None),
                       tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       _u=Depends(require_permissions("customer:view"))):
    items, total = await service.list_surveys(db, tenant_id, pageNo, pageSize, customer_id, industry, keyword)
    return ok({"items": [_survey_dict(s) for s in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/surveys")
async def create_survey(body: SurveyCreate, tenant_id: str = Depends(get_tenant_id),
                        db: AsyncSession = Depends(get_db), u=Depends(require_permissions("customer:edit"))):
    return ok(_survey_dict(await service.create_survey(db, tenant_id, body, u)))


@router.put("/surveys/{sid}")
async def update_survey(sid: str, body: SurveyUpdate, tenant_id: str = Depends(get_tenant_id),
                        db: AsyncSession = Depends(get_db), u=Depends(require_permissions("customer:edit"))):
    return ok(_survey_dict(await service.update_survey(db, tenant_id, sid, body, u)))


@router.delete("/surveys/{sid}")
async def delete_survey(sid: str, tenant_id: str = Depends(get_tenant_id),
                        db: AsyncSession = Depends(get_db), u=Depends(require_permissions("customer:edit"))):
    await service.delete_survey(db, tenant_id, sid, u)
    return ok()
