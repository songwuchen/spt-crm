from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR
from app.domains.customer.models import Customer, Contact, CustomerRelation, AclShare
from app.domains.customer.schemas import CustomerCreate, CustomerUpdate, ContactCreate, ContactUpdate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code


# ==================== Customer ====================

async def list_customers(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, industry: str | None = None,
    region: str | None = None, owner_id: str | None = None,
    tag: str | None = None,
    current_user: dict | None = None,
):
    base = select(Customer).where(Customer.tenant_id == tenant_id, Customer.is_deleted == False)
    if keyword:
        base = base.where(Customer.name.ilike(f"%{keyword}%"))
    if industry:
        base = base.where(Customer.industry == industry)
    if region:
        base = base.where(Customer.region.ilike(f"%{region}%"))
    if isinstance(owner_id, (list, tuple, set)):
        base = base.where(Customer.owner_id.in_(list(owner_id)))  # [] -> 无可见数据
    elif owner_id:
        base = base.where(Customer.owner_id == owner_id)
    if tag:
        from sqlalchemy import cast, String
        base = base.where(cast(Customer.tags_json, String).ilike(f"%{tag}%"))

    # Apply data scope (non-admin only sees owned/shared records)
    if current_user:
        from app.common.data_scope import apply_data_scope
        base = await apply_data_scope(base, db, tenant_id, current_user, Customer, "customer")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(Customer.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_customer(db: AsyncSession, tenant_id: str, customer_id: str) -> Customer:
    c = (await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id, Customer.is_deleted == False)
    )).scalar_one_or_none()
    if not c:
        raise BusinessException(code=NOT_FOUND, message="客户不存在")
    return c


async def create_customer(db: AsyncSession, tenant_id: str, data: CustomerCreate, user: dict) -> Customer:
    dump = data.model_dump()
    if not dump.get("customer_code"):
        dump["customer_code"] = await generate_code(db, tenant_id, "customer")
    # Resolve owner_name from owner_id if provided; default to creator
    owner_id = dump.pop("owner_id", None) or user.get("sub")
    owner_name = None
    if owner_id:
        from app.domains.auth.models import User
        owner = (await db.execute(
            select(User).where(User.id == owner_id, User.tenant_id == tenant_id)
        )).scalar_one_or_none()
        owner_name = owner.real_name or owner.username if owner else None
    customer = Customer(
        id=generate_uuid(), tenant_id=tenant_id,
        owner_id=owner_id, owner_name=owner_name,
        **dump,
    )
    db.add(customer)
    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.customer.created", "customer", customer.id, {
        "customer_id": customer.id, "customer_code": customer.customer_code, "name": customer.name,
    })
    await db.commit()
    await db.refresh(customer)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="customer", resource_id=customer.id,
                     summary=f"创建客户: {customer.name}")
    return customer


async def update_customer(db: AsyncSession, tenant_id: str, customer_id: str, data: CustomerUpdate, user: dict) -> Customer:
    customer = await get_customer(db, tenant_id, customer_id)
    update_data = data.model_dump(exclude_unset=True)
    # Resolve owner_name when owner_id changes
    if "owner_id" in update_data:
        new_owner_id = update_data["owner_id"]
        if new_owner_id:
            from app.domains.auth.models import User
            owner = (await db.execute(
                select(User).where(User.id == new_owner_id, User.tenant_id == tenant_id)
            )).scalar_one_or_none()
            update_data["owner_name"] = owner.real_name or owner.username if owner else None
        else:
            update_data["owner_name"] = None
    changes = {}
    for field, val in update_data.items():
        old_val = getattr(customer, field, None)
        if old_val != val:
            changes[field] = {"old": old_val, "new": val}
        setattr(customer, field, val)
    await db.commit()
    await db.refresh(customer)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="customer", resource_id=customer.id,
                     summary=f"更新客户: {customer.name}",
                     detail={"changes": changes} if changes else None)
    return customer


async def delete_customer(db: AsyncSession, tenant_id: str, customer_id: str, user: dict):
    from app.domains.project.models import OpportunityProject
    from app.domains.contract.models import Contract

    customer = await get_customer(db, tenant_id, customer_id)
    customer_name = customer.name

    # Check for active projects
    active_projects = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.customer_id == customer_id,
            OpportunityProject.status.in_(["active", "won"]),
        )
    )).scalar() or 0
    if active_projects > 0:
        raise BusinessException(code=VALIDATION_ERROR, message=f"该客户有 {active_projects} 个进行中/赢单商机，无法删除")

    # Check for signed contracts
    signed_contracts = (await db.execute(
        select(func.count(Contract.id)).where(
            Contract.tenant_id == tenant_id,
            Contract.project_id.in_(
                select(OpportunityProject.id).where(
                    OpportunityProject.customer_id == customer_id,
                    OpportunityProject.tenant_id == tenant_id,
                )
            ),
            Contract.status == "signed",
        )
    )).scalar() or 0
    if signed_contracts > 0:
        raise BusinessException(code=VALIDATION_ERROR, message=f"该客户有 {signed_contracts} 份已签合同，无法删除")

    # Clean up related data before soft-delete
    from sqlalchemy import delete as sql_delete
    await db.execute(
        sql_delete(AclShare).where(AclShare.tenant_id == tenant_id, AclShare.biz_type == "customer", AclShare.biz_id == customer_id)
    )
    await db.execute(
        sql_delete(CustomerRelation).where(
            CustomerRelation.tenant_id == tenant_id,
            (CustomerRelation.from_customer_id == customer_id) | (CustomerRelation.to_customer_id == customer_id),
        )
    )

    # Soft delete
    customer.is_deleted = True
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="customer", resource_id=customer_id,
                     summary=f"删除客户: {customer_name}")


# ==================== Customer Merge ====================

async def merge_customers(db: AsyncSession, tenant_id: str, primary_id: str, secondary_id: str, user: dict) -> Customer:
    """Merge secondary customer into primary. Moves contacts, projects, tickets, relations, shares."""
    if primary_id == secondary_id:
        raise BusinessException(code=VALIDATION_ERROR, message="不能合并同一个客户")

    primary = await get_customer(db, tenant_id, primary_id)
    secondary = await get_customer(db, tenant_id, secondary_id)

    from sqlalchemy import update
    from app.domains.project.models import OpportunityProject
    from app.domains.service_ticket.models import ServiceTicket

    # Move contacts
    await db.execute(
        update(Contact).where(Contact.tenant_id == tenant_id, Contact.customer_id == secondary_id)
        .values(customer_id=primary_id)
    )

    # Move projects
    await db.execute(
        update(OpportunityProject).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.customer_id == secondary_id
        ).values(customer_id=primary_id)
    )

    # Move service tickets
    await db.execute(
        update(ServiceTicket).where(
            ServiceTicket.tenant_id == tenant_id, ServiceTicket.customer_id == secondary_id
        ).values(customer_id=primary_id)
    )

    # Move relations (update from/to)
    await db.execute(
        update(CustomerRelation).where(
            CustomerRelation.tenant_id == tenant_id, CustomerRelation.from_customer_id == secondary_id
        ).values(from_customer_id=primary_id)
    )
    await db.execute(
        update(CustomerRelation).where(
            CustomerRelation.tenant_id == tenant_id, CustomerRelation.to_customer_id == secondary_id
        ).values(to_customer_id=primary_id)
    )

    # Move shares
    await db.execute(
        update(AclShare).where(
            AclShare.tenant_id == tenant_id, AclShare.biz_type == "customer", AclShare.biz_id == secondary_id
        ).values(biz_id=primary_id)
    )

    # Soft-delete secondary
    secondary.is_deleted = True
    await db.commit()
    await db.refresh(primary)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"],
                     user_name=user.get("real_name") or user.get("username"),
                     action="merge", resource_type="customer", resource_id=primary_id,
                     summary=f"合并客户: {secondary.name} → {primary.name}")
    return primary


# ==================== Customer Pool (公海池) ====================

async def list_pool_customers(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, industry: str | None = None, region: str | None = None,
):
    """List customers in the pool (no owner)."""
    base = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.is_deleted == False,
        Customer.status == "pool",
    )
    if keyword:
        base = base.where(Customer.name.ilike(f"%{keyword}%"))
    if industry:
        base = base.where(Customer.industry == industry)
    if region:
        base = base.where(Customer.region.ilike(f"%{region}%"))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(Customer.updated_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def release_to_pool(db: AsyncSession, tenant_id: str, customer_id: str, user: dict):
    """Release a customer to the pool."""
    customer = await get_customer(db, tenant_id, customer_id)
    if customer.status == "pool":
        raise BusinessException("客户已在公海池中")
    old_owner = customer.owner_name or customer.owner_id
    customer.status = "pool"
    customer.owner_id = None
    customer.owner_name = None
    await db.commit()
    await db.refresh(customer)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="release_to_pool", resource_type="customer", resource_id=customer.id,
                     summary=f"释放客户到公海: {customer.name} (原负责人: {old_owner})")
    return customer


async def claim_from_pool(db: AsyncSession, tenant_id: str, customer_id: str, user: dict):
    """Claim a customer from the pool."""
    customer = await get_customer(db, tenant_id, customer_id)
    if customer.status != "pool":
        raise BusinessException("客户不在公海池中")
    customer.status = "active"
    customer.owner_id = user["sub"]
    customer.owner_name = user.get("real_name") or user.get("username")
    await db.commit()
    await db.refresh(customer)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="claim_from_pool", resource_type="customer", resource_id=customer.id,
                     summary=f"从公海领取客户: {customer.name}")
    return customer


async def batch_release_to_pool(db: AsyncSession, tenant_id: str, customer_ids: list[str], user: dict):
    """Batch release customers to pool."""
    released = 0
    for cid in customer_ids:
        try:
            await release_to_pool(db, tenant_id, cid, user)
            released += 1
        except BusinessException:
            pass
    return released


# ==================== Contact ====================

async def list_contacts(db: AsyncSession, tenant_id: str, customer_id: str):
    result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.customer_id == customer_id)
        .order_by(Contact.is_primary.desc(), Contact.created_at)
    )
    return result.scalars().all()


async def create_contact(db: AsyncSession, tenant_id: str, customer_id: str, data: ContactCreate, user: dict) -> Contact:
    # Verify customer exists
    await get_customer(db, tenant_id, customer_id)

    contact = Contact(
        id=generate_uuid(), tenant_id=tenant_id,
        customer_id=customer_id, **data.model_dump(),
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="contact", resource_id=contact.id,
                     summary=f"创建联系人: {contact.name}")
    return contact


async def update_contact(db: AsyncSession, tenant_id: str, contact_id: str, data: ContactUpdate, user: dict) -> Contact:
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not contact:
        raise BusinessException(code=NOT_FOUND, message="联系人不存在")

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, val)
    await db.commit()
    await db.refresh(contact)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="contact", resource_id=contact.id,
                     summary=f"更新联系人: {contact.name}")
    return contact


async def delete_contact(db: AsyncSession, tenant_id: str, contact_id: str, user: dict):
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not contact:
        raise BusinessException(code=NOT_FOUND, message="联系人不存在")

    contact_name = contact.name
    await db.delete(contact)
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="contact", resource_id=contact_id,
                     summary=f"删除联系人: {contact_name}")


# ==================== Customer Relations ====================

async def list_relations(db: AsyncSession, tenant_id: str, customer_id: str):
    result = await db.execute(
        select(CustomerRelation).where(
            CustomerRelation.tenant_id == tenant_id,
            (CustomerRelation.from_customer_id == customer_id) | (CustomerRelation.to_customer_id == customer_id),
        ).order_by(CustomerRelation.created_at.desc())
    )
    return result.scalars().all()


async def create_relation(db: AsyncSession, tenant_id: str, data: dict, user: dict) -> CustomerRelation:
    rel = CustomerRelation(
        id=generate_uuid(), tenant_id=tenant_id,
        from_customer_id=data["from_customer_id"],
        to_customer_id=data["to_customer_id"],
        relation_type=data["relation_type"],
        note=data.get("note"),
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="customer_relation", resource_id=rel.id,
                     summary=f"创建客户关系: {data['relation_type']}")
    return rel


async def delete_relation(db: AsyncSession, tenant_id: str, relation_id: str, user: dict):
    rel = (await db.execute(
        select(CustomerRelation).where(CustomerRelation.id == relation_id, CustomerRelation.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rel:
        raise BusinessException(code=NOT_FOUND, message="客户关系不存在")
    await db.delete(rel)
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="customer_relation", resource_id=relation_id,
                     summary="删除客户关系")


# ==================== ACL Share ====================

async def list_shares(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str):
    result = await db.execute(
        select(AclShare).where(
            AclShare.tenant_id == tenant_id,
            AclShare.biz_type == biz_type,
            AclShare.biz_id == biz_id,
        ).order_by(AclShare.created_at.desc())
    )
    return result.scalars().all()


async def create_share(db: AsyncSession, tenant_id: str, data: dict, user: dict) -> AclShare:
    share = AclShare(
        id=generate_uuid(), tenant_id=tenant_id,
        biz_type=data["biz_type"], biz_id=data["biz_id"],
        shared_to_type=data["shared_to_type"],
        shared_to_id=data["shared_to_id"],
        shared_to_name=data.get("shared_to_name"),
        permission=data.get("permission", "view"),
        shared_by_id=user["sub"],
        shared_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share


async def delete_share(db: AsyncSession, tenant_id: str, share_id: str, user: dict):
    share = (await db.execute(
        select(AclShare).where(AclShare.id == share_id, AclShare.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not share:
        raise BusinessException(code=NOT_FOUND, message="共享记录不存在")
    await db.delete(share)
    await db.commit()
