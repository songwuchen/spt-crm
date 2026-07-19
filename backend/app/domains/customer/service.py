from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR
from app.domains.customer.models import Customer, Contact, CustomerRelation, AclShare, CustomerPool
from app.domains.customer.schemas import CustomerCreate, CustomerUpdate, ContactCreate, ContactUpdate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code


# ==================== 采购意向 / 归属 / 冗余指标 helpers ====================

# 采购意向类别（友商「客户类别」）推档：距今天数 → A/B/C/D，独立于价值等级 level。
# A=3个月内会订购(最热)，B=半年内，C=一年内，D=一年以上或已过期(最冷)。
INTENT_THRESHOLDS = (("A", 90), ("B", 180), ("C", 365))


def derive_intent_level(expected_purchase_date, today: date | None = None) -> str | None:
    """由预计采购时间推导采购意向类别 A/B/C/D。无日期返回 None。"""
    if not expected_purchase_date:
        return None
    if isinstance(expected_purchase_date, datetime):
        expected_purchase_date = expected_purchase_date.date()
    today = today or date.today()
    delta = (expected_purchase_date - today).days
    if delta < 0:
        return "D"  # 采购时间已过期，视为最冷
    for level, upper in INTENT_THRESHOLDS:
        if delta <= upper:
            return level
    return "D"


async def _resolve_owner_department(db: AsyncSession, tenant_id: str, owner_id: str | None):
    """解析负责人的（首个）所属部门，冗余到客户便于按部门统计/查询。"""
    if not owner_id:
        return None, None
    from app.domains.organization.models import UserDepartment, Department
    # 用户可能属多个部门：按加入时间取最早一个，保证冗余部门在多次编辑间稳定(否则 limit(1) 无序，结果可能抖动)
    dept_id = (await db.execute(
        select(UserDepartment.department_id).where(
            UserDepartment.tenant_id == tenant_id, UserDepartment.user_id == owner_id
        ).order_by(UserDepartment.created_at).limit(1)
    )).scalar_one_or_none()
    if not dept_id:
        return None, None
    dept = (await db.execute(
        select(Department).where(Department.id == dept_id, Department.tenant_id == tenant_id)
    )).scalar_one_or_none()
    return dept_id, (dept.name if dept else None)


async def refresh_won_deal_count(db: AsyncSession, tenant_id: str, customer_id: str) -> None:
    """重算并冗余客户「结单商机数」(status=won)。不提交，交由外层事务统一提交。"""
    from app.domains.project.models import OpportunityProject
    cnt = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.customer_id == customer_id,
            OpportunityProject.status == "won",
        )
    )).scalar() or 0
    cust = (await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if cust and (cust.won_deal_count or 0) != cnt:
        cust.won_deal_count = cnt


def match_pool(customer, pools):
    """按客户 region_code 前缀在已加载的公海列表中匹配区域公海；无匹配则回退默认公海(is_default)。
    返回 CustomerPool 或 None。纯内存计算，供释放/回收循环复用避免逐行查询。"""
    code = customer.region_code or ""
    default_pool = None
    for p in pools:
        if p.is_default and default_pool is None:
            default_pool = p
        scope = (p.region_scope or "").strip()
        if scope and code:
            for prefix in (x.strip() for x in scope.split(",")):
                if prefix and code.startswith(prefix):
                    return p
    return default_pool


async def list_active_pools(db: AsyncSession, tenant_id: str):
    return (await db.execute(
        select(CustomerPool).where(
            CustomerPool.tenant_id == tenant_id, CustomerPool.is_active == True
        ).order_by(CustomerPool.sort_order)
    )).scalars().all()


async def _route_pool_id(db: AsyncSession, tenant_id: str, customer) -> str | None:
    """按客户地区路由到区域公海 id；无任何公海配置时返回 None（=默认公海，兼容存量行为）。"""
    pools = await list_active_pools(db, tenant_id)
    if not pools:
        return None
    p = match_pool(customer, pools)
    return p.id if p else None


# ==================== Customer ====================

def _esc_like(s: str) -> str:
    """转义 LIKE 通配符，避免用户传入的 % / _ 改变匹配语义。"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_region_filter(stmt, region: str | None, region_code: str | None):
    """地区过滤：结构化编码前缀(region_code) 与 legacy 自由文本(region) 取并集(OR)，
    使已结构化与未回填的存量客户都能被同一次筛选命中。
    - region_code: 单个前缀(级联精确)或逗号分隔多个前缀(大区，如 '31,32,33')
    - region: 地区名称(省/市/区县名或大区名)，对 legacy 自由文本做包含匹配
    两者通配符均转义。"""
    from sqlalchemy import or_
    clauses = []
    if region_code:
        for p in (x.strip() for x in str(region_code).split(",")):
            if p:
                clauses.append(Customer.region_code.like(f"{_esc_like(p)}%", escape="\\"))
    if region:
        clauses.append(Customer.region.ilike(f"%{_esc_like(region)}%", escape="\\"))
    if clauses:
        stmt = stmt.where(or_(*clauses))
    return stmt


async def list_customers(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, industry: str | None = None,
    region: str | None = None, owner_id: str | None = None,
    tag: str | None = None,
    current_user: dict | None = None,
    adv_filter: str | None = None, sort_by: str | None = None, sort_order: str | None = None,
    region_code: str | None = None,
):
    base = select(Customer).where(Customer.tenant_id == tenant_id, Customer.is_deleted == False)
    if keyword:
        base = base.where(Customer.name.ilike(f"%{keyword}%"))
    if industry:
        base = base.where(Customer.industry == industry)
    # 地区过滤：结构化编码前缀 OR legacy 文本，兼顾已结构化与未回填的存量客户。
    base = _apply_region_filter(base, region, region_code)
    if isinstance(owner_id, (list, tuple, set)):
        base = base.where(Customer.owner_id.in_(list(owner_id)))  # [] -> 无可见数据
    elif owner_id:
        base = base.where(Customer.owner_id == owner_id)
    if tag:
        from sqlalchemy import cast, String
        base = base.where(cast(Customer.tags_json, String).ilike(f"%{tag}%"))

    # 高级筛选（多字段/多条件，含自定义扩展字段）
    from app.common.search import (
        entity_search_context, filter_clause_from_schema_or_400, resolve_sort_from_schema,
    )
    search_schema = await entity_search_context("customer", db, tenant_id)
    clause = filter_clause_from_schema_or_400(search_schema, adv_filter, {"user_id": (current_user or {}).get("sub")})
    if clause is not None:
        base = base.where(clause)

    # Apply data scope (non-admin only sees owned/shared records)
    if current_user:
        from app.common.data_scope import apply_data_scope
        base = await apply_data_scope(base, db, tenant_id, current_user, Customer, "customer")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    order = resolve_sort_from_schema(search_schema, sort_by, sort_order, Customer.created_at.desc())
    items = (await db.execute(
        base.order_by(order).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_customer(
    db: AsyncSession, tenant_id: str, customer_id: str, user: dict | None = None
) -> Customer:
    """按 id 取客户。传入 user 时校验数据范围（列表能查到的，按 id 才读得到）。

    user=None 表示系统内部调用（审批引擎/提醒/统计等），不做范围校验。
    """
    c = (await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id, Customer.is_deleted == False)
    )).scalar_one_or_none()
    if not c:
        raise BusinessException(code=NOT_FOUND, message="客户不存在")
    from app.common.data_scope import assert_in_scope
    await assert_in_scope(db, tenant_id, user, c, "customer", label="该客户")
    return c


async def create_customer(db: AsyncSession, tenant_id: str, data: CustomerCreate, user: dict) -> Customer:
    dump = data.model_dump()
    # 字段级权限：丢弃用户对不可编辑/隐藏扩展字段的写入
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    dump["custom_fields_json"] = await sanitize_entity_write(
        db, tenant_id, "customer", dump.get("custom_fields_json"), None, user.get("roles"))
    await validate_entity_custom_fields(
        db, tenant_id, "customer", dump["custom_fields_json"], user.get("roles"))
    # 原生字段策略：读取侧已按角色隐藏/脱敏，写入侧必须对称拦截，
    # 否则拿到 "***" 的用户一提交就会把真实值覆盖掉
    dump = await enforce_native_field_policy(db, tenant_id, "customer", dump, None, user.get("roles"))
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
    # 采购意向类别：未显式指定则由预计采购时间自动推档
    if not dump.get("intent_level"):
        dump["intent_level"] = derive_intent_level(dump.get("expected_purchase_date"))
    # 所属部门：冗余自负责人
    dept_id, dept_name = await _resolve_owner_department(db, tenant_id, owner_id)
    _uname = user.get("real_name") or user.get("username")
    customer = Customer(
        id=generate_uuid(), tenant_id=tenant_id,
        owner_id=owner_id, owner_name=owner_name,
        department_id=dept_id, department_name=dept_name,
        created_by_id=user.get("sub"),
        created_by_name=_uname,
        updated_by_id=user.get("sub"),
        updated_by_name=_uname,
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
    customer = await get_customer(db, tenant_id, customer_id, user)
    update_data = data.model_dump(exclude_unset=True)
    # 字段级权限：不可编辑扩展字段保留原值，忽略用户改动
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in update_data:
        update_data["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "customer", update_data["custom_fields_json"], customer.custom_fields_json, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "customer", update_data["custom_fields_json"], user.get("roles"))
    update_data = await enforce_native_field_policy(
        db, tenant_id, "customer", update_data, customer, user.get("roles"), required_scope="payload")
    # 最新修改人
    update_data["updated_by_id"] = user.get("sub")
    update_data["updated_by_name"] = user.get("real_name") or user.get("username")
    # 采购意向类别：改了采购时间且意向为空(未显式指定)时随之重算。
    # 注意用 not .get() 而非 "not in"——前端表单总会带上 intent_level 字段(可能为 null)，
    # 用 "not in" 会让自动推档在编辑态永远失效。
    if "expected_purchase_date" in update_data and not update_data.get("intent_level"):
        update_data["intent_level"] = derive_intent_level(update_data["expected_purchase_date"])
    # Resolve owner_name when owner_id changes
    reassigned_to = None
    if "owner_id" in update_data:
        new_owner_id = update_data["owner_id"]
        if new_owner_id:
            from app.domains.auth.models import User
            owner = (await db.execute(
                select(User).where(User.id == new_owner_id, User.tenant_id == tenant_id)
            )).scalar_one_or_none()
            update_data["owner_name"] = owner.real_name or owner.username if owner else None
            if new_owner_id != customer.owner_id:
                reassigned_to = new_owner_id
        else:
            update_data["owner_name"] = None
        # 所属部门随负责人同步冗余
        dept_id, dept_name = await _resolve_owner_department(db, tenant_id, new_owner_id)
        update_data["department_id"] = dept_id
        update_data["department_name"] = dept_name
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
    # 客户转给他人 → 通知新负责人
    if reassigned_to and reassigned_to != user["sub"]:
        try:
            from app.common.auto_notify import notify_customer_assigned
            await notify_customer_assigned(db, tenant_id, customer.name, reassigned_to,
                                           user.get("real_name") or user.get("username"), customer.id)
        except Exception:
            pass
    return customer


async def delete_customer(db: AsyncSession, tenant_id: str, customer_id: str, user: dict):
    from app.domains.project.models import OpportunityProject
    from app.domains.contract.models import Contract

    customer = await get_customer(db, tenant_id, customer_id, user)
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

    primary = await get_customer(db, tenant_id, primary_id, user)
    secondary = await get_customer(db, tenant_id, secondary_id, user)

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
    # 次客户的商机已并入主客户 → 重算主客户的「结单商机数」冗余，避免合并后计数偏低
    await refresh_won_deal_count(db, tenant_id, primary_id)
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
    region_code: str | None = None, pool_id: str | None = None,
):
    """List customers in the pool (no owner). pool_id='__default__' 表示归属默认公海(pool_id 为空)。"""
    base = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.is_deleted == False,
        Customer.status == "pool",
    )
    if keyword:
        base = base.where(Customer.name.ilike(f"%{keyword}%"))
    if industry:
        base = base.where(Customer.industry == industry)
    if pool_id == "__default__":
        base = base.where(Customer.pool_id.is_(None))
    elif pool_id:
        base = base.where(Customer.pool_id == pool_id)
    base = _apply_region_filter(base, region, region_code)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(Customer.updated_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def release_to_pool(db: AsyncSession, tenant_id: str, customer_id: str, user: dict, pools=None):
    """Release a customer to the pool. 传入预加载的 pools 可避免批量释放时逐客户查询公海列表。"""
    customer = await get_customer(db, tenant_id, customer_id, user)
    if customer.status == "pool":
        raise BusinessException(message="客户已在公海池中")
    old_owner = customer.owner_name or customer.owner_id
    customer.status = "pool"
    customer.owner_id = None
    customer.owner_name = None
    customer.department_id = None
    customer.department_name = None
    customer.pool_source = "manual_release"
    customer.pool_entered_at = datetime.now(timezone.utc)
    if pools is None:
        pools = await list_active_pools(db, tenant_id)
    matched = match_pool(customer, pools) if pools else None
    customer.pool_id = matched.id if matched else None
    await db.commit()
    await db.refresh(customer)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="release_to_pool", resource_type="customer", resource_id=customer.id,
                     summary=f"释放客户到公海: {customer.name} (原负责人: {old_owner})")
    return customer


async def claim_from_pool(db: AsyncSession, tenant_id: str, customer_id: str, user: dict):
    """Claim a customer from the pool."""
    # 公海客户对全员可见（is_in_scope 放行 status='pool'），领取动作本身不受归属限制
    customer = await get_customer(db, tenant_id, customer_id, user)
    if customer.status != "pool":
        raise BusinessException(message="客户不在公海池中")
    customer.status = "active"
    customer.owner_id = user["sub"]
    customer.owner_name = user.get("real_name") or user.get("username")
    dept_id, dept_name = await _resolve_owner_department(db, tenant_id, user["sub"])
    customer.department_id = dept_id
    customer.department_name = dept_name
    customer.pool_id = None
    customer.pool_source = None
    customer.pool_entered_at = None
    await db.commit()
    await db.refresh(customer)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="claim_from_pool", resource_type="customer", resource_id=customer.id,
                     summary=f"从公海领取客户: {customer.name}")
    return customer


async def batch_release_to_pool(db: AsyncSession, tenant_id: str, customer_ids: list[str], user: dict):
    """Batch release customers to pool."""
    pools = await list_active_pools(db, tenant_id)  # 加载一次，复用于每个客户的归池匹配
    released = 0
    for cid in customer_ids:
        try:
            await release_to_pool(db, tenant_id, cid, user, pools=pools)
            released += 1
        except BusinessException:
            pass
    return released


# ==================== Contact ====================

async def _load_contact_scoped(
    db: AsyncSession, tenant_id: str, contact_id: str, user: dict | None
) -> Contact:
    """取联系人并按「所属客户」的可见性校验。

    Contact 自身没有 owner_id，可见性只能由父客户决定；同时这里不接受调用方传来的
    customer_id 作为凭据——历史上路由把 /customers/{cid}/contacts/{id} 的 cid 直接丢弃，
    导致任意 cid 都能改到任意联系人。
    """
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not contact:
        raise BusinessException(code=NOT_FOUND, message="联系人不存在")
    if user is not None and contact.customer_id:
        await get_customer(db, tenant_id, contact.customer_id, user)  # 越权即 403
    return contact


async def list_contacts(db: AsyncSession, tenant_id: str, customer_id: str, user: dict | None = None):
    if user is not None:
        await get_customer(db, tenant_id, customer_id, user)  # 父客户不可见则不给列联系人
    result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.customer_id == customer_id)
        .order_by(Contact.is_primary.desc(), Contact.created_at)
    )
    return result.scalars().all()


async def create_contact(db: AsyncSession, tenant_id: str, customer_id: str, data: ContactCreate, user: dict) -> Contact:
    # Verify customer exists（并且在本人数据范围内——否则可给他人客户挂联系人）
    await get_customer(db, tenant_id, customer_id, user)

    dump = data.model_dump()
    # 字段级权限：丢弃用户对不可编辑/隐藏扩展字段的写入
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    dump["custom_fields_json"] = await sanitize_entity_write(
        db, tenant_id, "contact", dump.get("custom_fields_json"), None, user.get("roles"))
    await validate_entity_custom_fields(
        db, tenant_id, "contact", dump["custom_fields_json"], user.get("roles"))
    dump = await enforce_native_field_policy(db, tenant_id, "contact", dump, None, user.get("roles"))
    contact = Contact(
        id=generate_uuid(), tenant_id=tenant_id,
        customer_id=customer_id, **dump,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="contact", resource_id=contact.id,
                     summary=f"创建联系人: {contact.name}")
    return contact


async def update_contact(db: AsyncSession, tenant_id: str, contact_id: str, data: ContactUpdate, user: dict) -> Contact:
    contact = await _load_contact_scoped(db, tenant_id, contact_id, user)

    _dump = data.model_dump(exclude_unset=True)
    # 字段级权限：不可编辑扩展字段保留原值，忽略用户改动
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in _dump:
        _dump["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "contact", _dump["custom_fields_json"], contact.custom_fields_json, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "contact", _dump["custom_fields_json"], user.get("roles"))
    _dump = await enforce_native_field_policy(
        db, tenant_id, "contact", _dump, contact, user.get("roles"), required_scope="payload")
    for field, val in _dump.items():
        setattr(contact, field, val)
    await db.commit()
    await db.refresh(contact)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="contact", resource_id=contact.id,
                     summary=f"更新联系人: {contact.name}")
    return contact


async def delete_contact(db: AsyncSession, tenant_id: str, contact_id: str, user: dict):
    contact = await _load_contact_scoped(db, tenant_id, contact_id, user)

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


# ==================== Customer Pool 配置(区域公海) ====================

async def list_pools(db: AsyncSession, tenant_id: str):
    return (await db.execute(
        select(CustomerPool).where(CustomerPool.tenant_id == tenant_id)
        .order_by(CustomerPool.sort_order, CustomerPool.created_at)
    )).scalars().all()


async def _clear_default_pool(db: AsyncSession, tenant_id: str, exclude_id: str | None = None):
    from sqlalchemy import update as sql_update
    stmt = sql_update(CustomerPool).where(
        CustomerPool.tenant_id == tenant_id, CustomerPool.is_default == True
    )
    if exclude_id:
        stmt = stmt.where(CustomerPool.id != exclude_id)
    await db.execute(stmt.values(is_default=False))


async def create_pool(db: AsyncSession, tenant_id: str, data: dict, user: dict) -> CustomerPool:
    if data.get("is_default"):
        await _clear_default_pool(db, tenant_id)
    pool = CustomerPool(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(pool)
    await db.commit()
    await db.refresh(pool)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="customer_pool", resource_id=pool.id,
                     summary=f"创建区域公海: {pool.name}")
    return pool


async def update_pool(db: AsyncSession, tenant_id: str, pool_id: str, data: dict, user: dict) -> CustomerPool:
    pool = (await db.execute(
        select(CustomerPool).where(CustomerPool.id == pool_id, CustomerPool.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not pool:
        raise BusinessException(code=NOT_FOUND, message="公海不存在")
    if data.get("is_default"):
        await _clear_default_pool(db, tenant_id, exclude_id=pool_id)
    for field, val in data.items():
        setattr(pool, field, val)
    await db.commit()
    await db.refresh(pool)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="customer_pool", resource_id=pool.id,
                     summary=f"更新区域公海: {pool.name}")
    return pool


async def delete_pool(db: AsyncSession, tenant_id: str, pool_id: str, user: dict):
    pool = (await db.execute(
        select(CustomerPool).where(CustomerPool.id == pool_id, CustomerPool.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not pool:
        raise BusinessException(code=NOT_FOUND, message="公海不存在")
    # 归属该公海的客户回落默认公海(pool_id=NULL)，不丢失客户
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(Customer).where(Customer.tenant_id == tenant_id, Customer.pool_id == pool_id)
        .values(pool_id=None)
    )
    name = pool.name
    await db.delete(pool)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="customer_pool", resource_id=pool_id,
                     summary=f"删除区域公海: {name}")


async def pool_counts(db: AsyncSession, tenant_id: str) -> dict:
    """各区域公海当前在库客户数(status=pool)，含默认公海(键 '__default__')。"""
    rows = (await db.execute(
        select(Customer.pool_id, func.count(Customer.id)).where(
            Customer.tenant_id == tenant_id, Customer.is_deleted == False, Customer.status == "pool"
        ).group_by(Customer.pool_id)
    )).all()
    return {(pid or "__default__"): cnt for pid, cnt in rows}
