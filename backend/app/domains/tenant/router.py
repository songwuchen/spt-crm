from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
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
    tenant_id: str = Depends(get_tenant_id),
    _user=Depends(require_permissions("tenant:view")),
):
    """平台租户列表。

    这是个跨租户接口：返回的是全平台租户的名称/编码/套餐/联系人电话邮箱，本身没有任何
    tenant 过滤。守卫是 tenant:view——而 tenant:view 很容易被顺手勾进业务角色里
    （生产上销售内勤、生产主任这类角色都持有它），一旦平台上不止一个租户，
    这个接口就是跨租户通讯录。

    因此这里按「是否真的是平台管理员(tenant:manage)」分流：
    平台管理员看全部，其余人只看得到自己所属的那个租户。
    单租户环境下两者结果相同，属于纯加固。
    """
    only_own = "*" not in (_user.get("permissions") or []) \
        and "tenant:manage" not in (_user.get("permissions") or [])
    items, total = await list_tenants(
        db, pageNo, pageSize, only_tenant_id=tenant_id if only_own else None)
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
