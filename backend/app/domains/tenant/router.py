from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_permissions
from app.common.schemas import ok
from app.domains.tenant.schemas import TenantCreate, TenantOut, TenantStatusUpdate
from app.domains.tenant.service import create_tenant, list_tenants, update_tenant_status

router = APIRouter(prefix="/api/admin/v1/platform/tenants", tags=["租户管理"])


@router.post("")
async def create(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("tenant:manage")),
):
    tenant = await create_tenant(db, body)
    return ok(TenantOut.model_validate(tenant).model_dump())


@router.get("")
async def list_all(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("tenant:view")),
):
    items, total = await list_tenants(db, pageNo, pageSize)
    return ok({
        "items": [TenantOut.model_validate(t).model_dump() for t in items],
        "total": total, "pageNo": pageNo, "pageSize": pageSize,
    })


@router.post("/{tenant_id}/status")
async def update_status(
    tenant_id: str,
    body: TenantStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("tenant:manage")),
):
    tenant = await update_tenant_status(db, tenant_id, body.is_active)
    return ok(TenantOut.model_validate(tenant).model_dump())
