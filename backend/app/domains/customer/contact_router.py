"""Standalone contact list — cross-customer contact search and management."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions
from app.common.schemas import ok
from app.domains.customer.models import Contact, Customer

router = APIRouter(prefix="/api/v1/contacts", tags=["联系人"])


@router.get("")
async def list_contacts(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    role_type: str = Query(None),
    customer_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contact:view")),
):
    q = select(Contact).where(Contact.tenant_id == tenant_id, Contact.is_deleted == False)
    count_q = select(func.count(Contact.id)).where(Contact.tenant_id == tenant_id, Contact.is_deleted == False)

    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            (Contact.name.ilike(like)) | (Contact.phone.ilike(like)) |
            (Contact.mobile.ilike(like)) | (Contact.email.ilike(like))
        )
        count_q = count_q.where(
            (Contact.name.ilike(like)) | (Contact.phone.ilike(like)) |
            (Contact.mobile.ilike(like)) | (Contact.email.ilike(like))
        )
    if role_type:
        q = q.where(Contact.role_type == role_type)
        count_q = count_q.where(Contact.role_type == role_type)
    if customer_id:
        q = q.where(Contact.customer_id == customer_id)
        count_q = count_q.where(Contact.customer_id == customer_id)

    total = (await db.execute(count_q)).scalar() or 0
    items = (await db.execute(
        q.order_by(Contact.created_at.desc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).scalars().all()

    # Batch-fetch customer names
    cust_ids = list({c.customer_id for c in items if c.customer_id})
    cust_map: dict[str, str] = {}
    if cust_ids:
        rows = (await db.execute(
            select(Customer.id, Customer.name).where(Customer.id.in_(cust_ids))
        )).all()
        cust_map = {r[0]: r[1] for r in rows}

    return ok({
        "items": [{
            "id": c.id, "customer_id": c.customer_id,
            "customer_name": cust_map.get(c.customer_id, ""),
            "name": c.name, "title": c.title, "role_type": c.role_type,
            "phone": c.phone, "mobile": c.mobile, "email": c.email,
            "is_primary": c.is_primary, "remark": c.remark,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        } for c in items],
        "total": total, "pageNo": pageNo, "pageSize": pageSize,
    })
