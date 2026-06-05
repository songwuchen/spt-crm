"""售后现场实测数据 service。"""
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.common.code_generator import generate_code
from app.domains.audit.service import log_action
from app.domains.measurement.models import ServiceMeasurement
from app.domains.measurement.schemas import MeasurementCreate, MeasurementUpdate

logger = logging.getLogger("spt_crm.measurement")


async def list_measurements(db, tenant_id, page_no=1, page_size=20, customer_id=None,
                            ticket_id=None, equipment_model=None, industry=None, keyword=None):
    base = select(ServiceMeasurement).where(ServiceMeasurement.tenant_id == tenant_id)
    if customer_id:
        base = base.where(ServiceMeasurement.customer_id == customer_id)
    if ticket_id:
        base = base.where(ServiceMeasurement.ticket_id == ticket_id)
    if equipment_model:
        base = base.where(ServiceMeasurement.equipment_model == equipment_model)
    if industry:
        base = base.where(ServiceMeasurement.industry == industry)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(
            ServiceMeasurement.customer_name.ilike(kw) | ServiceMeasurement.equipment_model.ilike(kw)
            | ServiceMeasurement.equipment_name.ilike(kw) | ServiceMeasurement.material_name.ilike(kw)
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(ServiceMeasurement.service_date.desc().nullslast(), ServiceMeasurement.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_measurement(db, tenant_id, mid) -> ServiceMeasurement:
    m = (await db.execute(
        select(ServiceMeasurement).where(ServiceMeasurement.id == mid, ServiceMeasurement.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not m:
        raise BusinessException(code=NOT_FOUND, message="实测记录不存在")
    return m


async def create_measurement(db, tenant_id, data: MeasurementCreate, user: dict) -> ServiceMeasurement:
    dump = data.model_dump(exclude_unset=True)
    if not dump.get("record_no"):
        dump["record_no"] = await generate_code(db, tenant_id, "measurement")
    m = ServiceMeasurement(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **dump,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="measurement", resource_id=m.id,
                     summary=f"录入实测数据: {m.record_no}")
    return m


async def update_measurement(db, tenant_id, mid, data: MeasurementUpdate, user: dict) -> ServiceMeasurement:
    m = await get_measurement(db, tenant_id, mid)
    for f, v in data.model_dump(exclude_unset=True).items():
        setattr(m, f, v)
    await db.commit()
    await db.refresh(m)
    return m


async def delete_measurement(db, tenant_id, mid, user: dict):
    m = await get_measurement(db, tenant_id, mid)
    await db.delete(m)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="measurement", resource_id=mid,
                     summary=f"删除实测数据: {m.record_no}")


async def stats_by_model(db, tenant_id, limit=50):
    """按设备型号聚合：记录数、平均筛分效率、平均处理量、平均运行电流。"""
    rows = (await db.execute(
        select(
            ServiceMeasurement.equipment_model,
            func.count(ServiceMeasurement.id).label("cnt"),
            func.avg(ServiceMeasurement.screen_efficiency).label("avg_eff"),
            func.avg(ServiceMeasurement.throughput_tph).label("avg_tph"),
            func.avg(ServiceMeasurement.running_current_a).label("avg_cur"),
        ).where(
            ServiceMeasurement.tenant_id == tenant_id,
            ServiceMeasurement.equipment_model != None,  # noqa: E711
        ).group_by(ServiceMeasurement.equipment_model)
        .order_by(func.count(ServiceMeasurement.id).desc()).limit(limit)
    )).all()
    return [{
        "equipment_model": r.equipment_model, "count": r.cnt,
        "avg_efficiency": round(float(r.avg_eff), 2) if r.avg_eff is not None else None,
        "avg_throughput": round(float(r.avg_tph), 2) if r.avg_tph is not None else None,
        "avg_current": round(float(r.avg_cur), 2) if r.avg_cur is not None else None,
    } for r in rows]
