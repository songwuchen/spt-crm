"""Open API service layer: app management, call logging, and read queries.

Read queries filter strictly by ``tenant_id`` (+ ``is_deleted == False`` where the
model has it) so an app can only ever see its own tenant's data. Results are handed
to the DTO layer before leaving the process.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.crypto import encrypt_value
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.openapi.models import OpenApiApp, OpenApiCallLog
from app.domains.openapi.schemas import OpenApiAppCreate, OpenApiAppUpdate
from app.domains.openapi.auth import hash_secret, generate_app_key, generate_secret

from app.domains.customer.models import Customer, Contact
from app.domains.project.models import OpportunityProject, ProjectStageHistory
from app.domains.contract.models import Contract, ContractVersion
from app.domains.lead.models import Lead
from app.domains.product.models import Product
from app.domains.order.models import Order
from app.domains.quote.models import Quote, QuoteVersion, QuoteLine
from app.domains.payment.models import PaymentRecord
from app.domains.service_ticket.models import ServiceTicket
from app.domains.delivery.models import DeliveryMilestone
from app.domains.activity.models import Activity
from app.domains.outbox.models import OutboxEvent
from app.domains.admin.models import WebhookSubscription


# ============================================================ app management
def app_to_dict(app: OpenApiApp) -> dict:
    """Admin-facing view of an app — never includes secret_hash / secret_enc."""
    return {
        "id": app.id,
        "app_key": app.app_key,
        "name": app.name,
        "app_type": app.app_type,
        "auth_mode": app.auth_mode,
        "status": app.status,
        "scopes": app.scopes_json or [],
        "secret_prefix": app.secret_prefix,
        "rate_limit_per_minute": app.rate_limit_per_minute,
        "ip_whitelist": app.ip_whitelist_json or [],
        "remark": app.remark,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }


async def list_apps(db: AsyncSession, tenant_id: str) -> list[OpenApiApp]:
    rows = (await db.execute(
        select(OpenApiApp)
        .where(OpenApiApp.tenant_id == tenant_id, OpenApiApp.is_deleted == False)  # noqa: E712
        .order_by(OpenApiApp.created_at.desc())
    )).scalars().all()
    return list(rows)


async def _get_app(db: AsyncSession, tenant_id: str, app_id: str) -> OpenApiApp:
    app = (await db.execute(
        select(OpenApiApp).where(
            OpenApiApp.id == app_id,
            OpenApiApp.tenant_id == tenant_id,
            OpenApiApp.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not app:
        raise BusinessException(code=NOT_FOUND, message="应用不存在")
    return app


async def create_app(db: AsyncSession, tenant_id: str, data: OpenApiAppCreate) -> tuple[OpenApiApp, str]:
    """Create an app and return (app, plaintext_secret). The secret is shown ONCE."""
    secret = generate_secret()
    app = OpenApiApp(
        id=generate_uuid(),
        tenant_id=tenant_id,
        app_key=generate_app_key(),
        name=data.name,
        app_type=data.app_type,
        auth_mode=data.auth_mode,
        status="enabled",
        scopes_json=data.scopes,
        secret_hash=hash_secret(secret),
        secret_enc=encrypt_value(secret),
        secret_prefix=secret[:12],
        rate_limit_per_minute=data.rate_limit_per_minute,
        ip_whitelist_json=data.ip_whitelist,
        remark=data.remark,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app, secret


async def update_app(db: AsyncSession, tenant_id: str, app_id: str, data: OpenApiAppUpdate) -> OpenApiApp:
    app = await _get_app(db, tenant_id, app_id)
    patch = data.model_dump(exclude_unset=True)
    if "name" in patch:
        app.name = patch["name"]
    if "status" in patch:
        app.status = patch["status"]
    if "auth_mode" in patch:
        app.auth_mode = patch["auth_mode"]
    if "scopes" in patch:
        app.scopes_json = patch["scopes"]
    if "rate_limit_per_minute" in patch:
        app.rate_limit_per_minute = patch["rate_limit_per_minute"]
    if "ip_whitelist" in patch:
        app.ip_whitelist_json = patch["ip_whitelist"]
    if "remark" in patch:
        app.remark = patch["remark"]
    await db.commit()
    await db.refresh(app)
    return app


async def regenerate_secret(db: AsyncSession, tenant_id: str, app_id: str) -> tuple[OpenApiApp, str]:
    """Rotate the secret. The old key is invalidated immediately."""
    app = await _get_app(db, tenant_id, app_id)
    secret = generate_secret()
    app.secret_hash = hash_secret(secret)
    app.secret_enc = encrypt_value(secret)
    app.secret_prefix = secret[:12]
    await db.commit()
    await db.refresh(app)
    return app, secret


async def delete_app(db: AsyncSession, tenant_id: str, app_id: str) -> None:
    app = await _get_app(db, tenant_id, app_id)
    app.is_deleted = True
    await db.commit()


# ================================================================ call logs
async def write_call_log(
    db: AsyncSession, *, tenant_id: str, app_key: str, trace_id: str | None,
    method: str, path: str, query_string: str | None, status_code: int | None,
    error_code: str | None, duration_ms: int | None, client_ip: str | None,
) -> None:
    db.add(OpenApiCallLog(
        id=generate_uuid(), tenant_id=tenant_id, trace_id=trace_id, app_key=app_key,
        method=method, path=path, query_string=(query_string or None),
        status_code=status_code, error_code=error_code,
        duration_ms=duration_ms, client_ip=client_ip,
    ))
    await db.commit()


async def list_call_logs(
    db: AsyncSession, tenant_id: str, *, app_key: str | None = None,
    page: int = 1, page_size: int = 20,
):
    base = select(OpenApiCallLog).where(OpenApiCallLog.tenant_id == tenant_id)
    if app_key:
        base = base.where(OpenApiCallLog.app_key == app_key)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (await db.execute(
        base.order_by(OpenApiCallLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


# ================================================================== queries
def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def query_customers(
    db: AsyncSession, tenant_id: str, *, keyword: str | None, status: str | None,
    customer_code: str | None, updated_since: str | None, page: int, page_size: int,
):
    base = select(Customer).where(
        Customer.tenant_id == tenant_id, Customer.is_deleted == False,  # noqa: E712
    )
    if keyword:
        like = f"%{keyword}%"
        base = base.where(or_(Customer.name.ilike(like), Customer.customer_code.ilike(like)))
    if status:
        base = base.where(Customer.status == status)
    if customer_code:
        base = base.where(Customer.customer_code == customer_code)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(Customer.updated_at >= dt)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (await db.execute(
        base.order_by(Customer.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def get_customer(db: AsyncSession, tenant_id: str, customer_id: str) -> Customer | None:
    return (await db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == tenant_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def query_contacts(
    db: AsyncSession, tenant_id: str, *, customer_id: str | None, page: int, page_size: int,
):
    base = select(Contact).where(Contact.tenant_id == tenant_id)
    if customer_id:
        base = base.where(Contact.customer_id == customer_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (await db.execute(
        base.order_by(Contact.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def query_projects(
    db: AsyncSession, tenant_id: str, *, customer_id: str | None, stage_code: str | None,
    status: str | None, updated_since: str | None = None, page: int = 1, page_size: int = 20,
):
    base = select(OpportunityProject).where(
        OpportunityProject.tenant_id == tenant_id,
        OpportunityProject.is_deleted == False,  # noqa: E712
    )
    if customer_id:
        base = base.where(OpportunityProject.customer_id == customer_id)
    if stage_code:
        base = base.where(OpportunityProject.stage_code == stage_code)
    if status:
        base = base.where(OpportunityProject.status == status)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(OpportunityProject.updated_at >= dt)
    return await _paginate(db, base, OpportunityProject.updated_at, page, page_size)


async def get_project(db: AsyncSession, tenant_id: str, project_id: str) -> OpportunityProject | None:
    return (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.id == project_id,
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def query_contracts(
    db: AsyncSession, tenant_id: str, *, project_id: str | None, status: str | None,
    updated_since: str | None = None, page: int = 1, page_size: int = 20,
):
    base = select(Contract).where(Contract.tenant_id == tenant_id)
    if project_id:
        base = base.where(Contract.project_id == project_id)
    if status:
        base = base.where(Contract.status == status)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(Contract.updated_at >= dt)
    return await _paginate(db, base, Contract.updated_at, page, page_size)


async def get_contract(db: AsyncSession, tenant_id: str, contract_id: str) -> Contract | None:
    return (await db.execute(
        select(Contract).where(
            Contract.id == contract_id, Contract.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()


# ==================================================================== events
async def query_events(
    db: AsyncSession, tenant_id: str, *, event_type: str | None, after_event_id: str | None,
    occurred_from: str | None, occurred_to: str | None, limit: int,
):
    """Cursor pagination by (created_at, id). ``after_event_id`` resolves to the
    referenced event's created_at and returns strictly newer events."""
    base = select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id)
    if event_type:
        base = base.where(OutboxEvent.event_type == event_type)
    df = _parse_dt(occurred_from)
    if df:
        base = base.where(OutboxEvent.created_at >= df)
    dt_ = _parse_dt(occurred_to)
    if dt_:
        base = base.where(OutboxEvent.created_at <= dt_)
    if after_event_id:
        cursor = (await db.execute(
            select(OutboxEvent).where(
                OutboxEvent.id == after_event_id, OutboxEvent.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if cursor and cursor.created_at is not None:
            base = base.where(
                or_(
                    OutboxEvent.created_at > cursor.created_at,
                    (OutboxEvent.created_at == cursor.created_at) & (OutboxEvent.id > cursor.id),
                )
            )
    rows = (await db.execute(
        base.order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc()).limit(limit)
    )).scalars().all()
    return list(rows)


async def get_event(db: AsyncSession, tenant_id: str, event_id: str) -> OutboxEvent | None:
    return (await db.execute(
        select(OutboxEvent).where(
            OutboxEvent.id == event_id, OutboxEvent.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()


# ===================================================== additional reads
async def _paginate(db, base, order_col, page: int, page_size: int):
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (await db.execute(
        base.order_by(order_col.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def _get_one(db, model, tenant_id: str, obj_id: str):
    return (await db.execute(
        select(model).where(model.id == obj_id, model.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def query_products(db, tenant_id, *, keyword, is_active, updated_since=None, page=1, page_size=20):
    base = select(Product).where(Product.tenant_id == tenant_id)
    if keyword:
        base = base.where(or_(Product.name.ilike(f"%{keyword}%"), Product.product_code.ilike(f"%{keyword}%")))
    if is_active is not None:
        base = base.where(Product.is_active == is_active)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(Product.updated_at >= dt)
    return await _paginate(db, base, Product.updated_at, page, page_size)


async def get_product(db, tenant_id, obj_id):
    return await _get_one(db, Product, tenant_id, obj_id)


async def query_orders(db, tenant_id, *, customer_id, status, updated_since=None, page=1, page_size=20):
    base = select(Order).where(Order.tenant_id == tenant_id, Order.is_deleted == False)  # noqa: E712
    if customer_id:
        base = base.where(Order.customer_id == customer_id)
    if status:
        base = base.where(Order.status == status)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(Order.updated_at >= dt)
    return await _paginate(db, base, Order.updated_at, page, page_size)


async def get_order(db, tenant_id, obj_id):
    o = await _get_one(db, Order, tenant_id, obj_id)
    return o if (o and not o.is_deleted) else None


async def query_quotes(db, tenant_id, *, project_id, status, updated_since=None, page=1, page_size=20):
    base = select(Quote).where(Quote.tenant_id == tenant_id)
    if project_id:
        base = base.where(Quote.project_id == project_id)
    if status:
        base = base.where(Quote.status == status)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(Quote.updated_at >= dt)
    return await _paginate(db, base, Quote.updated_at, page, page_size)


async def get_quote(db, tenant_id, obj_id):
    return await _get_one(db, Quote, tenant_id, obj_id)


async def get_quote_lines(db, tenant_id, quote_id):
    """Return (quote, version, lines) for the quote's current version, or (None, None, [])."""
    quote = await _get_one(db, Quote, tenant_id, quote_id)
    if not quote:
        return None, None, []
    version = (await db.execute(
        select(QuoteVersion).where(
            QuoteVersion.tenant_id == tenant_id,
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.version_no == quote.current_version_no,
        )
    )).scalar_one_or_none()
    if not version:
        return quote, None, []
    lines = (await db.execute(
        select(QuoteLine).where(
            QuoteLine.tenant_id == tenant_id,
            QuoteLine.quote_version_id == version.id,
        ).order_by(QuoteLine.line_no.asc())
    )).scalars().all()
    return quote, version, list(lines)


async def query_payments(db, tenant_id, *, project_id, page, page_size):
    base = select(PaymentRecord).where(PaymentRecord.tenant_id == tenant_id)
    if project_id:
        base = base.where(PaymentRecord.project_id == project_id)
    return await _paginate(db, base, PaymentRecord.created_at, page, page_size)


async def list_quote_versions(db, tenant_id, quote_id):
    """Return version rows for a quote (newest first), or None if quote missing."""
    if not await _get_one(db, Quote, tenant_id, quote_id):
        return None
    rows = (await db.execute(
        select(QuoteVersion).where(
            QuoteVersion.tenant_id == tenant_id, QuoteVersion.quote_id == quote_id,
        ).order_by(QuoteVersion.version_no.desc())
    )).scalars().all()
    return list(rows)


async def list_contract_versions(db, tenant_id, contract_id):
    if not await _get_one(db, Contract, tenant_id, contract_id):
        return None
    rows = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id == contract_id,
        ).order_by(ContractVersion.version_no.desc())
    )).scalars().all()
    return list(rows)


async def list_stage_history(db, tenant_id, project_id):
    if not await _get_one(db, OpportunityProject, tenant_id, project_id):
        return None
    rows = (await db.execute(
        select(ProjectStageHistory).where(
            ProjectStageHistory.tenant_id == tenant_id, ProjectStageHistory.project_id == project_id,
        ).order_by(ProjectStageHistory.created_at.asc())
    )).scalars().all()
    return list(rows)


async def query_service_tickets(db, tenant_id, *, customer_id, status, updated_since=None, page=1, page_size=20):
    base = select(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id)
    if customer_id:
        base = base.where(ServiceTicket.customer_id == customer_id)
    if status:
        base = base.where(ServiceTicket.status == status)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(ServiceTicket.updated_at >= dt)
    return await _paginate(db, base, ServiceTicket.updated_at, page, page_size)


async def get_service_ticket(db, tenant_id, obj_id):
    return await _get_one(db, ServiceTicket, tenant_id, obj_id)


async def query_milestones(db, tenant_id, *, project_id, page, page_size):
    base = select(DeliveryMilestone).where(DeliveryMilestone.tenant_id == tenant_id)
    if project_id:
        base = base.where(DeliveryMilestone.project_id == project_id)
    return await _paginate(db, base, DeliveryMilestone.sort_order, page, page_size)


# ============================================================ writes (leads)
async def create_lead_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create a lead from an external app. Reuses the internal lead service so all
    business rules (code generation, scoring, audit) apply. The lead is attributed
    to the app and left unassigned (pool) for sales to claim."""
    from app.domains.lead.service import create_lead
    from app.domains.lead.schemas import LeadCreate
    from app.domains.openapi.dto import lead_to_dto

    pseudo_user = {
        "sub": ctx.app_id,  # AuditLog.user_id is non-null; attribute to the app
        "username": f"openapi:{ctx.app_key}",
        "real_name": "开放平台",
    }
    lead = await create_lead(db, ctx.tenant_id, LeadCreate(**data.model_dump(exclude_unset=True)), pseudo_user)
    # create_lead defaults owner to the creator (here the app id); de-own into the pool.
    if lead.owner_id == ctx.app_id:
        lead.owner_id = None
        lead.owner_name = "开放平台（待分配）"
        await db.commit()
        await db.refresh(lead)
    return lead_to_dto(lead)


def _pseudo_user(ctx) -> dict:
    return {"sub": ctx.app_id, "username": f"openapi:{ctx.app_key}", "real_name": "开放平台"}


async def create_activity_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Log a follow-up/activity on a customer/project/lead via the internal service."""
    from app.domains.activity.service import create_activity
    from app.domains.activity.schemas import ActivityCreate
    from app.domains.openapi.dto import activity_to_dto
    payload = data.model_dump(exclude_unset=True)
    act = await create_activity(db, ctx.tenant_id, ActivityCreate(**payload), _pseudo_user(ctx))
    return activity_to_dto(act)


async def create_customer_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create a customer (unassigned/public pool) via the internal service."""
    from app.domains.customer.service import create_customer
    from app.domains.customer.schemas import CustomerCreate
    from app.domains.openapi.dto import customer_to_dto
    payload = data.model_dump(exclude_unset=True)
    customer = await create_customer(db, ctx.tenant_id, CustomerCreate(**payload), _pseudo_user(ctx))
    if customer.owner_id == ctx.app_id:
        customer.owner_id = None
        customer.owner_name = "开放平台（待分配）"
        await db.commit()
        await db.refresh(customer)
    return customer_to_dto(customer)


async def qualify_lead_from_openapi(db: AsyncSession, ctx, lead_id: str) -> dict:
    from app.domains.lead.service import qualify_lead
    return await qualify_lead(db, ctx.tenant_id, lead_id, _pseudo_user(ctx))


async def discard_lead_from_openapi(db: AsyncSession, ctx, lead_id: str) -> dict:
    from app.domains.lead.service import discard_lead
    from app.domains.openapi.dto import lead_to_dto
    lead = await discard_lead(db, ctx.tenant_id, lead_id, _pseudo_user(ctx))
    return lead_to_dto(lead)


async def create_service_ticket_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create a support ticket via the internal service (SLA timers + code apply)."""
    from app.domains.service_ticket.service import create_ticket
    from app.domains.service_ticket.schemas import ServiceTicketCreate
    from app.domains.openapi.dto import service_ticket_to_dto
    payload = data.model_dump(exclude_unset=True)
    ticket = await create_ticket(db, ctx.tenant_id, ServiceTicketCreate(**payload), _pseudo_user(ctx))
    return service_ticket_to_dto(ticket)


# ============================================================ webhook ops
def _compute_webhook_sig(secret: str, body: str) -> str:
    import hmac as _hmac, hashlib as _hashlib
    return _hmac.new(secret.encode(), body.encode(), _hashlib.sha256).hexdigest()


async def send_test_webhook(db: AsyncSession, tenant_id: str, subscription_id: str) -> dict:
    """Send a signed sample event to a subscription's callback URL, matching the
    format the outbox worker uses (so integrators can validate their receiver)."""
    import json
    import httpx
    sub = (await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not sub:
        raise BusinessException(code=NOT_FOUND, message="订阅不存在")

    payload = {
        "event_id": "evt_test",
        "event_type": "crm.webhook.test",
        "aggregate_type": "webhook",
        "aggregate_id": subscription_id,
        "tenant_id": tenant_id,
        "timestamp": datetime.now().isoformat(),
        "data": {"message": "这是一条 SPT-CRM 开放平台测试推送"},
    }
    body = json.dumps(payload, ensure_ascii=False, default=str)
    headers = {"Content-Type": "application/json"}
    if sub.secret_token:
        headers["X-Webhook-Signature"] = "sha256=" + _compute_webhook_sig(sub.secret_token, body)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(sub.target_url, content=body, headers=headers)
            return {
                "status_code": resp.status_code,
                "success": 200 <= resp.status_code < 300,
                "response_body": resp.text[:500],
            }
    except httpx.TimeoutException:
        return {"status_code": 0, "success": False, "response_body": "请求超时"}
    except Exception as e:  # noqa: BLE001
        return {"status_code": 0, "success": False, "response_body": str(e)[:300]}
