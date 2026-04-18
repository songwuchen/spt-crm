"""Standalone contact list — cross-customer contact search and management."""
import csv
import io

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions
from app.common.schemas import ok
from app.database import generate_uuid
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
    q = select(Contact).where(Contact.tenant_id == tenant_id)
    count_q = select(func.count(Contact.id)).where(Contact.tenant_id == tenant_id)

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


@router.post("/import")
async def import_contacts(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contact:create")),
):
    """Import contacts from CSV file. Matches customers by name."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    # Pre-fetch all customer name -> id mapping for this tenant
    cust_rows = (await db.execute(
        select(Customer.id, Customer.name).where(
            Customer.tenant_id == tenant_id,
            Customer.is_deleted == False,
        )
    )).all()
    cust_map: dict[str, str] = {r[1].strip(): r[0] for r in cust_rows}

    success = 0
    errors: list[dict] = []
    valid_role_types = {"decision_maker", "influencer", "user", "finance", "procurement"}

    for idx, row in enumerate(reader, start=2):  # row 1 is header
        customer_name = (row.get("customer_name") or "").strip()
        name = (row.get("name") or "").strip()

        if not customer_name:
            errors.append({"row": idx, "reason": "缺少 customer_name"})
            continue
        if not name:
            errors.append({"row": idx, "reason": "缺少 name"})
            continue

        customer_id = cust_map.get(customer_name)
        if not customer_id:
            errors.append({"row": idx, "reason": f"未找到客户: {customer_name}"})
            continue

        role_type = (row.get("role_type") or "").strip() or None
        if role_type and role_type not in valid_role_types:
            errors.append({"row": idx, "reason": f"无效的角色类型: {role_type}"})
            continue

        is_primary_raw = (row.get("is_primary") or "").strip().lower()
        is_primary = is_primary_raw in ("true", "1", "是", "yes")

        contact = Contact(
            id=generate_uuid(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            name=name,
            title=(row.get("title") or "").strip() or None,
            role_type=role_type,
            phone=(row.get("phone") or "").strip() or None,
            mobile=(row.get("mobile") or "").strip() or None,
            email=(row.get("email") or "").strip() or None,
            is_primary=is_primary,
            remark=(row.get("remark") or "").strip() or None,
        )
        db.add(contact)
        success += 1

    if success > 0:
        await db.commit()

    return ok({
        "success": success,
        "failed": len(errors),
        "total": success + len(errors),
        "errors": errors,
    })
