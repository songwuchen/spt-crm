"""扩展平台 — 仪表盘服务(CRUD)。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.database import generate_uuid
from app.domains.lowcode.dashboard_models import Dashboard
from app.domains.lowcode import dashboard_schemas as ds


async def create(db: AsyncSession, tenant_id: str, data: ds.DashboardCreate, user: dict) -> Dashboard:
    d = Dashboard(id=generate_uuid(), tenant_id=tenant_id, name=data.name,
                  description=data.description, components=[], styles={}, created_by=user.get("sub"))
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def get(db: AsyncSession, tenant_id: str, dash_id: str) -> Dashboard:
    d = (await db.execute(select(Dashboard).where(
        Dashboard.id == dash_id, Dashboard.tenant_id == tenant_id,
        Dashboard.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not d:
        raise BusinessException(code=NOT_FOUND, message="仪表盘不存在")
    return d


async def list_(db: AsyncSession, tenant_id: str, page_no: int, page_size: int):
    conds = [Dashboard.tenant_id == tenant_id, Dashboard.is_deleted == False]  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(Dashboard).where(*conds))).scalar_one()
    rows = (await db.execute(select(Dashboard).where(*conds)
            .order_by(Dashboard.sort_order.asc(), Dashboard.created_at.desc())
            .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return list(rows), total


async def update(db: AsyncSession, tenant_id: str, dash_id: str, data: ds.DashboardUpdate) -> Dashboard:
    d = await get(db, tenant_id, dash_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    await db.commit()
    await db.refresh(d)
    return d


async def delete(db: AsyncSession, tenant_id: str, dash_id: str) -> None:
    d = await get(db, tenant_id, dash_id)
    d.is_deleted = True
    await db.commit()
