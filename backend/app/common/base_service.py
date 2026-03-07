"""
Base CRUD service utilities for standardizing service layer patterns.

Provides reusable functions that eliminate boilerplate across domain services:
  - paginated_query: standard list with pagination
  - get_or_404: fetch one record or raise BusinessException
  - update_fields: partial update from Pydantic model
  - soft_delete: set is_deleted=True

Usage:
    from app.common.base_service import paginated_query, get_or_404, update_fields, soft_delete

    async def list_items(db, tenant_id, page_no, page_size, keyword=None):
        q = select(MyModel).where(MyModel.tenant_id == tenant_id, MyModel.is_deleted == False)
        if keyword:
            q = q.where(MyModel.name.ilike(f"%{keyword}%"))
        return await paginated_query(db, q, page_no, page_size)

    async def get_item(db, tenant_id, item_id):
        return await get_or_404(db, MyModel, tenant_id, item_id, label="记录")
"""
from typing import Any, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND

T = TypeVar("T")


async def paginated_query(
    db: AsyncSession,
    query,
    page_no: int = 1,
    page_size: int = 20,
    order_by=None,
) -> tuple[list, int]:
    """Execute a query with pagination, returning (items, total)."""
    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar() or 0

    q = query
    if order_by is not None:
        q = q.order_by(order_by)
    q = q.offset((page_no - 1) * page_size).limit(page_size)

    items = (await db.execute(q)).scalars().all()
    return items, total


async def get_or_404(
    db: AsyncSession,
    model: type[T],
    tenant_id: str,
    record_id: str,
    label: str = "记录",
    check_deleted: bool = True,
) -> T:
    """Fetch a single tenant-scoped record by ID, or raise NOT_FOUND."""
    conditions = [
        model.tenant_id == tenant_id,  # type: ignore
        model.id == record_id,  # type: ignore
    ]
    if check_deleted and hasattr(model, "is_deleted"):
        conditions.append(model.is_deleted == False)  # type: ignore  # noqa: E712

    result = (await db.execute(select(model).where(*conditions))).scalar_one_or_none()
    if not result:
        raise BusinessException(code=NOT_FOUND, message=f"{label}不存在")
    return result


def update_fields(instance: Any, data: dict, exclude: set[str] | None = None) -> bool:
    """Apply partial updates from a dict to a model instance.

    Returns True if any field was changed.
    """
    changed = False
    exclude = exclude or set()
    for key, value in data.items():
        if key in exclude:
            continue
        if hasattr(instance, key) and getattr(instance, key) != value:
            setattr(instance, key, value)
            changed = True
    return changed


async def soft_delete(
    db: AsyncSession,
    model: type,
    tenant_id: str,
    record_id: str,
    label: str = "记录",
) -> None:
    """Soft-delete a record by setting is_deleted=True."""
    record = await get_or_404(db, model, tenant_id, record_id, label=label)
    record.is_deleted = True  # type: ignore
    await db.commit()


async def hard_delete(
    db: AsyncSession,
    model: type,
    tenant_id: str,
    record_id: str,
    label: str = "记录",
) -> None:
    """Permanently delete a record."""
    record = await get_or_404(db, model, tenant_id, record_id, label=label, check_deleted=False)
    await db.delete(record)
    await db.commit()
