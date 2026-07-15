"""扩展平台 — 仪表盘 API。前缀 /api/v1/lc/dashboards。

- 仪表盘设计/管理: dashboard:view / dashboard:manage
- 聚合取数: form_data:view(能看表单数据者即可取图表数据)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions, get_current_user
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.common.error_codes import FORBIDDEN
from app.domains.lowcode import dashboard_schemas as ds, dashboard_service as dsvc
from app.domains.lowcode.aggregation import aggregate
from app.domains.lowcode.crm_aggregation import aggregate_crm, get_registry, entity_perm

router = APIRouter(prefix="/api/v1/lc/dashboards", tags=["扩展平台-仪表盘"])


def _dash(d):
    return ds.DashboardOut.model_validate(d).model_dump()


@router.get("")
async def list_dashboards(pageNo: int = Query(1, ge=1), pageSize: int = Query(50, ge=1, le=100),
                          tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                          _u=Depends(require_permissions("dashboard:view"))):
    items, total = await dsvc.list_(db, tenant_id, pageNo, pageSize)
    return ok({"items": [_dash(d) for d in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("")
async def create_dashboard(body: ds.DashboardCreate, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), user: dict = Depends(require_permissions("dashboard:manage"))):
    return ok(_dash(await dsvc.create(db, tenant_id, body, user)))


@router.get("/crm-sources")
async def crm_sources(_u=Depends(require_permissions("dashboard:view"))):
    """可图表化的 CRM 业务实体及其维度/指标(供仪表盘配置)。放在 /{dash_id} 之前,避免被动态路由捕获。"""
    return ok(get_registry())


@router.get("/{dash_id}")
async def get_dashboard(dash_id: str, tenant_id: str = Depends(get_tenant_id),
                        db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("dashboard:view"))):
    return ok(_dash(await dsvc.get(db, tenant_id, dash_id)))


@router.put("/{dash_id}")
async def update_dashboard(dash_id: str, body: ds.DashboardUpdate, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("dashboard:manage"))):
    return ok(_dash(await dsvc.update(db, tenant_id, dash_id, body)))


@router.delete("/{dash_id}")
async def delete_dashboard(dash_id: str, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("dashboard:manage"))):
    await dsvc.delete(db, tenant_id, dash_id)
    return ok(None)


@router.post("/aggregate")
async def aggregate_data(body: ds.AggregateRequest, tenant_id: str = Depends(get_tenant_id),
                         db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("form_data:view"))):
    result = await aggregate(
        db, tenant_id, body.template_id,
        [d.model_dump() for d in body.dimensions],
        [m.model_dump() for m in body.metrics],
        [f.model_dump() for f in body.filters],
        body.limit,
    )
    return ok(result)


@router.post("/aggregate-crm")
async def aggregate_crm_data(body: ds.CrmAggregateRequest, tenant_id: str = Depends(get_tenant_id),
                             db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """对 CRM 业务数据(客户/线索/订单...)聚合。需具备该实体的查看权限。"""
    perm = entity_perm(body.entity)
    if perm and perm not in (user.get("permissions") or []):
        raise BusinessException(code=FORBIDDEN, message=f"缺少权限: {perm}")
    result = await aggregate_crm(
        db, tenant_id, body.entity,
        [d.model_dump() for d in body.dimensions],
        [m.model_dump() for m in body.metrics],
        [f.model_dump() for f in body.filters],
        body.limit,
    )
    return ok(result)
