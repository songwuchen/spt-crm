from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import DUPLICATE_ENTRY, NOT_FOUND
from app.database import generate_uuid
from app.domains.tenant.models import PlatformTenant
from app.domains.tenant.schemas import TenantCreate


async def create_tenant(db: AsyncSession, data: TenantCreate) -> PlatformTenant:
    existing = (await db.execute(
        select(PlatformTenant).where(PlatformTenant.code == data.code)
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"租户编码 {data.code} 已存在")

    tenant = PlatformTenant(id=generate_uuid(), **data.model_dump())
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def list_tenants(db: AsyncSession, page_no: int = 1, page_size: int = 20,
                       only_tenant_id: str | None = None):
    """列平台租户。only_tenant_id 非空时只返回该租户（非平台管理员的调用方）。"""
    count_q = select(func.count(PlatformTenant.id))
    query = select(PlatformTenant)
    if only_tenant_id:
        count_q = count_q.where(PlatformTenant.id == only_tenant_id)
        query = query.where(PlatformTenant.id == only_tenant_id)
    total = (await db.execute(count_q)).scalar()
    query = query.order_by(PlatformTenant.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return items, total


async def update_tenant_status(db: AsyncSession, tenant_id: str, is_active: bool) -> PlatformTenant:
    tenant = (await db.execute(select(PlatformTenant).where(PlatformTenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise BusinessException(code=NOT_FOUND, message="租户不存在")
    tenant.is_active = is_active
    await db.commit()
    await db.refresh(tenant)
    return tenant
