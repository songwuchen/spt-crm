from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.measurement import service
from app.domains.measurement.schemas import MeasurementCreate, MeasurementUpdate

router = APIRouter(prefix="/api/v1/measurements", tags=["售后实测数据"])


def _m_dict(m) -> dict:
    f = lambda v: float(v) if v is not None else None  # noqa: E731
    return {
        "id": m.id, "record_no": m.record_no, "ticket_id": m.ticket_id,
        "customer_id": m.customer_id, "customer_name": m.customer_name,
        "service_date": str(m.service_date) if m.service_date else None,
        "engineer_id": m.engineer_id, "engineer_name": m.engineer_name,
        "industry": m.industry,
        "equipment_name": m.equipment_name, "equipment_model": m.equipment_model, "product_no": m.product_no,
        "motor_power_kw": f(m.motor_power_kw), "amplitude_mm": f(m.amplitude_mm),
        "material_name": m.material_name, "layer_thickness_mm": f(m.layer_thickness_mm),
        "feed_size_mm": f(m.feed_size_mm), "screen_efficiency": f(m.screen_efficiency),
        "throughput_tph": f(m.throughput_tph), "source_temp_c": f(m.source_temp_c),
        "ambient_temp_c": f(m.ambient_temp_c), "running_current_a": f(m.running_current_a),
        "daily_run_hours": f(m.daily_run_hours),
        "service_rating": m.service_rating, "product_rating": m.product_rating,
        "result_desc": m.result_desc, "issues": m.issues, "remark": m.remark,
        "created_by_name": m.created_by_name,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    }


@router.get("/stats")
async def stats(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                _u=Depends(require_permissions("service:view"))):
    return ok(await service.stats_by_model(db, tenant_id))


@router.get("/export/excel")
async def export_excel(customer_id: str = Query(None), equipment_model: str = Query(None),
                       industry: str = Query(None), keyword: str = Query(None),
                       tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       _u=Depends(require_permissions("service:view"))):
    from app.config import settings
    items, _ = await service.list_measurements(db, tenant_id, 1, settings.MAX_EXPORT_ROWS,
                                               customer_id, None, equipment_model, industry, keyword)
    headers = ["记录号", "客户", "服务日期", "行业", "设备名称", "设备型号", "物料",
               "筛分效率%", "处理量t/h", "运行电流A", "振源温度", "日运行h", "服务人员"]
    rows = []
    for m in items:
        rows.append([
            m.record_no, m.customer_name or "", str(m.service_date) if m.service_date else "",
            m.industry or "", m.equipment_name or "", m.equipment_model or "", m.material_name or "",
            float(m.screen_efficiency) if m.screen_efficiency is not None else "",
            float(m.throughput_tph) if m.throughput_tph is not None else "",
            float(m.running_current_a) if m.running_current_a is not None else "",
            float(m.source_temp_c) if m.source_temp_c is not None else "",
            float(m.daily_run_hours) if m.daily_run_hours is not None else "",
            m.engineer_name or "",
        ])
    buf = build_excel("售后实测数据", headers, rows)
    return excel_response(buf, "measurements.xlsx")


@router.get("")
async def list_measurements(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                            customer_id: str = Query(None), ticket_id: str = Query(None),
                            equipment_model: str = Query(None), industry: str = Query(None), keyword: str = Query(None),
                            tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                            _u=Depends(require_permissions("service:view"))):
    items, total = await service.list_measurements(db, tenant_id, pageNo, pageSize, customer_id,
                                                   ticket_id, equipment_model, industry, keyword)
    return ok({"items": [_m_dict(m) for m in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("")
async def create_measurement(body: MeasurementCreate, tenant_id: str = Depends(get_tenant_id),
                             db: AsyncSession = Depends(get_db), u=Depends(require_permissions("service:edit"))):
    return ok(_m_dict(await service.create_measurement(db, tenant_id, body, u)))


@router.get("/{mid}")
async def get_measurement(mid: str, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("service:view"))):
    return ok(_m_dict(await service.get_measurement(db, tenant_id, mid)))


@router.put("/{mid}")
async def update_measurement(mid: str, body: MeasurementUpdate, tenant_id: str = Depends(get_tenant_id),
                             db: AsyncSession = Depends(get_db), u=Depends(require_permissions("service:edit"))):
    return ok(_m_dict(await service.update_measurement(db, tenant_id, mid, body, u)))


@router.delete("/{mid}")
async def delete_measurement(mid: str, tenant_id: str = Depends(get_tenant_id),
                             db: AsyncSession = Depends(get_db), u=Depends(require_permissions("service:edit"))):
    await service.delete_measurement(db, tenant_id, mid, u)
    return ok()
