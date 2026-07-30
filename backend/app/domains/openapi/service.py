"""Open API service layer: app management, call logging, and read queries.

Read queries filter strictly by ``tenant_id`` (+ ``is_deleted == False`` where the
model has it) so an app can only ever see its own tenant's data. Results are handed
to the DTO layer before leaving the process.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.crypto import encrypt_value
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.openapi.models import OpenApiApp, OpenApiCallLog
from app.domains.openapi.schemas import OpenApiAppCreate, OpenApiAppUpdate
from app.domains.openapi.auth import hash_secret, generate_app_key, generate_secret
from app.domains.openapi.errors import OpenApiException, CRM_DUPLICATE_ENTRY

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
async def resolve_department_id(
    db: AsyncSession, tenant_id: str, *, department_id: str | None, department_name: str | None,
) -> str | None:
    """Map open-API department fields onto a CRM department UUID.

    Prefer explicit ``department_id`` (validated against the tenant). Otherwise
    resolve ``department_name`` by exact match against DingTalk-synced departments
    (name trimmed). Ambiguous / missing names yield None — the lead is still created
    without a department rather than failing the whole write.
    """
    import logging
    from app.domains.organization.models import Department

    log = logging.getLogger(__name__)
    if department_id:
        dept = (await db.execute(
            select(Department).where(
                Department.id == department_id, Department.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if dept:
            return dept.id
        log.warning("openapi lead: department_id %s not found in tenant %s", department_id, tenant_id)
        return None

    name = (department_name or "").strip()
    if not name:
        return None
    rows = (await db.execute(
        select(Department).where(
            Department.tenant_id == tenant_id, Department.name == name,
        ).order_by(Department.path)
    )).scalars().all()
    if not rows:
        log.warning("openapi lead: department_name %r not found in tenant %s", name, tenant_id)
        return None
    if len(rows) > 1:
        log.warning(
            "openapi lead: department_name %r matched %d departments; using %s (%s)",
            name, len(rows), rows[0].id, rows[0].path,
        )
    return rows[0].id


async def resolve_user_id(
    db: AsyncSession, tenant_id: str, *, user_id: str | None, user_name: str | None,
    field_label: str = "user",
) -> str | None:
    """Map open-API user fields onto a CRM user UUID.

    Prefer explicit ``user_id``. Otherwise resolve ``user_name`` by exact match on
    ``real_name`` or ``username`` (DingTalk-synced users). Missing → None.
    """
    import logging
    from app.domains.auth.models import User as AuthUser

    log = logging.getLogger(__name__)
    if user_id:
        u = (await db.execute(
            select(AuthUser).where(
                AuthUser.id == user_id, AuthUser.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if u:
            return u.id
        log.warning("openapi lead: %s_id %s not found in tenant %s", field_label, user_id, tenant_id)
        return None

    name = (user_name or "").strip()
    if not name:
        return None
    u = (await db.execute(
        select(AuthUser).where(
            AuthUser.tenant_id == tenant_id,
            (AuthUser.real_name == name) | (AuthUser.username == name),
        )
    )).scalars().first()
    if not u:
        log.warning("openapi lead: %s_name %r not found in tenant %s", field_label, name, tenant_id)
        return None
    return u.id


async def resolve_owner_id(
    db: AsyncSession, tenant_id: str, *, owner_id: str | None, owner_name: str | None,
) -> str | None:
    return await resolve_user_id(
        db, tenant_id, user_id=owner_id, user_name=owner_name, field_label="owner",
    )


async def resolve_reporter_id(
    db: AsyncSession, tenant_id: str, *, reporter_id: str | None, reporter_name: str | None,
) -> str | None:
    return await resolve_user_id(
        db, tenant_id, user_id=reporter_id, user_name=reporter_name, field_label="reporter",
    )


# 简道云申报信息「客户类型」常见简称 / 历史写法 → 字典码（与 seed_lead_dicts 对齐）。
_CUSTOMER_TYPE_ALIASES = {
    "终端-央企国企": "terminal_soe",
    "终端客户-央企国企": "terminal_soe",
    "央企/国企": "terminal_soe",
    "大型民企": "terminal_large_private",
    "终端客户-大型民企": "terminal_large_private",
    "一般民企": "terminal_private",
    "终端客户—一般民企": "terminal_private",  # em-dash variant seen in JDY history
    "总包": "general_contractor",
    "配套贸易": "supporting_trader",
    "配套商": "supporting_trader",
    "贸易商": "supporting_trader",
    "supporting_vendor": "supporting_trader",
    "trader": "supporting_trader",
}


def _normalize_customer_type_text(raw: str) -> str:
    """Trim and unify dash variants so label/alias lookup is stable."""
    s = (raw or "").strip()
    if not s:
        return ""
    return s.replace("—", "-").replace("–", "-")


async def resolve_customer_type(db: AsyncSession, tenant_id: str, raw: str | None) -> str | None:
    """Map OpenAPI customer_type (code or Chinese label) to dict_code.

    Resolution order: empty → None; exact dict_code; exact dict_label; static
    aliases; otherwise keep the original string (do not block sync).
    """
    if raw is None:
        return None
    text = _normalize_customer_type_text(raw)
    if not text:
        return None

    from app.domains.admin.models import DataDictionary

    rows = (
        await db.execute(
            select(DataDictionary.dict_code, DataDictionary.dict_label).where(
                DataDictionary.tenant_id == tenant_id,
                DataDictionary.dict_type == "customer_type",
                DataDictionary.is_deleted == False,  # noqa: E712
                DataDictionary.enabled == True,  # noqa: E712
            )
        )
    ).all()
    by_code = {r.dict_code: r.dict_code for r in rows if r.dict_code}
    by_label = {_normalize_customer_type_text(r.dict_label): r.dict_code for r in rows if r.dict_label}
    if text in by_code:
        return by_code[text]
    if text in by_label:
        return by_label[text]
    alias = _CUSTOMER_TYPE_ALIASES.get(text) or _CUSTOMER_TYPE_ALIASES.get(raw.strip())
    if alias:
        return alias
    return text


async def _resolve_lead_write_payload(db: AsyncSession, ctx, data) -> dict:
    """Shared open-API lead field resolution (dept / owner / reporter names → ids)."""
    payload = data.model_dump(exclude_unset=True)
    dept_name = payload.pop("department_name", None)
    raw_dept_id = payload.pop("department_id", None)
    resolved_dept = await resolve_department_id(
        db, ctx.tenant_id, department_id=raw_dept_id, department_name=dept_name,
    )
    if resolved_dept:
        payload["department_id"] = resolved_dept

    owner_name = payload.pop("owner_name", None)
    raw_owner_id = payload.pop("owner_id", None)
    resolved_owner = await resolve_owner_id(
        db, ctx.tenant_id, owner_id=raw_owner_id, owner_name=owner_name,
    )
    if resolved_owner:
        payload["owner_id"] = resolved_owner

    reporter_name = payload.pop("reporter_name", None)
    raw_reporter_id = payload.pop("reporter_id", None)
    if not raw_reporter_id and not (reporter_name or "").strip():
        raw_reporter_id = resolved_owner or raw_owner_id
        reporter_name = owner_name
    resolved_reporter = await resolve_reporter_id(
        db, ctx.tenant_id, reporter_id=raw_reporter_id, reporter_name=reporter_name,
    )
    if resolved_reporter:
        payload["reporter_id"] = resolved_reporter

    if "customer_type" in payload:
        payload["customer_type"] = await resolve_customer_type(
            db, ctx.tenant_id, payload.get("customer_type"),
        )
    return payload


async def create_lead_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create a lead from an external app. Reuses the internal lead service so all
    business rules (code generation, scoring, audit) apply.

    If ``owner_id`` / ``owner_name`` resolve to a CRM user, the lead is assigned to
    that user (简道云「申报人」→ CRM 负责人). Otherwise it is left in the open pool.
    ``reporter_*`` maps the same JianDaoYun申报人 onto CRM 报备人 when provided.
    """
    from app.domains.lead.service import create_lead
    from app.domains.lead.schemas import LeadCreate
    from app.domains.openapi.dto import lead_to_dto

    payload = await _resolve_lead_write_payload(db, ctx, data)
    lead = await create_lead(db, ctx.tenant_id, LeadCreate(**payload), _pseudo_user(ctx))
    # create_lead defaults owner to the creator (here the app id) when none resolved;
    # de-own into the pool only in that case.
    if lead.owner_id == ctx.app_id:
        lead.owner_id = None
        lead.owner_name = "开放平台（待分配）"
        await db.commit()
        await db.refresh(lead)
    # 报备人若落成开放平台伪用户，同样清空（无真实申报人时不伪装成「开放平台」人名）
    if lead.reporter_id == ctx.app_id:
        lead.reporter_id = None
        lead.reporter_name = None
        await db.commit()
        await db.refresh(lead)
    return lead_to_dto(lead)


async def update_lead_from_openapi(db: AsyncSession, ctx, lead_id: str, data) -> dict:
    """Update an existing open-API lead (e.g. idempotent replay with a richer body).

    Only resolved department / owner / reporter ids and reported_at (plus other
    provided scalar fields) are written; unresolved names do not clear existing
    assignments.
    """
    from app.domains.lead.service import update_lead
    from app.domains.lead.schemas import LeadUpdate
    from app.domains.openapi.dto import lead_to_dto

    payload = await _resolve_lead_write_payload(db, ctx, data)
    # Don't blank owner/dept when name resolution fails on a backfill replay.
    for k in ("department_id", "owner_id", "reporter_id"):
        if k in payload and not payload[k]:
            payload.pop(k)
    lead = await update_lead(db, ctx.tenant_id, lead_id, LeadUpdate(**payload), _pseudo_user(ctx))
    return lead_to_dto(lead)


def _pseudo_user(ctx) -> dict:
    """开放平台调用内部 service 时的伪用户。

    必须带 SYSTEM_ROLE：内部 service 会跑按登录用户角色的字段级权限，若这里给空角色集，
    任何配了 visible_roles/unmask_roles 的字段都会被判为「无交集 → 隐藏/脱敏」，
    导致外部集成提交的值被静默丢弃（接口却返回成功）；租户配的必填也会把此前能用的
    集成直接拒掉。调用方已过 app_key 鉴权，字段策略这层对它不适用。
    """
    from app.domains.lowcode.field_permission import SYSTEM_ROLE
    return {
        "sub": ctx.app_id, "username": f"openapi:{ctx.app_key}", "real_name": "开放平台",
        "roles": [SYSTEM_ROLE],
        # data scope: SYSTEM_ROLE alone is not admin; without this, update_lead →
        # get_lead → assert_in_scope would 403 on leads not owned by the app id.
        "permissions": ["data:view_all"],
    }


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


async def create_order_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create an order via the internal service; leave unassigned (pool)."""
    from app.domains.order.service import create_order
    from app.domains.order.schemas import OrderCreate
    from app.domains.openapi.dto import order_to_dto
    payload = data.model_dump(exclude_unset=True)
    order = await create_order(db, ctx.tenant_id, OrderCreate(**payload), _pseudo_user(ctx))
    if order.owner_id == ctx.app_id:
        order.owner_id = None
        order.owner_name = "开放平台（待分配）"
        await db.commit()
        await db.refresh(order)
    return order_to_dto(order)


async def update_order_status_from_openapi(db: AsyncSession, ctx, order_id: str, status: str) -> dict:
    """Status write-back (e.g. ERP marks order shipped/completed)."""
    from app.domains.order.service import update_order
    from app.domains.order.schemas import OrderUpdate
    from app.domains.openapi.dto import order_to_dto
    order = await update_order(db, ctx.tenant_id, order_id, OrderUpdate(status=status), _pseudo_user(ctx))
    return order_to_dto(order)


def _to_date(value: str | None):
    """Parse an ISO date or datetime string into a date; None on empty/invalid.
    Accepts both '2026-06-01' and '2026-06-01T16:00:00.000Z' (JianDaoYun) forms."""
    from datetime import date as _date, datetime as _dt
    if not value:
        return None
    s = value.strip()
    try:
        return _date.fromisoformat(s[:10])
    except ValueError:
        try:
            return _dt.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            return None


async def _apply_openapi_contract_fields(db: AsyncSession, tenant_id: str, contract: Contract, data) -> None:
    """Copy OpenAPI intake fields onto an existing Contract (in-memory only)."""
    contract.customer_id = data.customer_id
    if data.project_id is not None:
        contract.project_id = data.project_id
    if data.status is not None:
        contract.status = data.status
    if data.signed_date is not None:
        contract.signed_date = _to_date(data.signed_date)
    if data.end_date is not None:
        contract.end_date = _to_date(data.end_date)
    if data.amount_total is not None:
        contract.amount_total = data.amount_total
    if getattr(data, "drawing_no", None) is not None:
        contract.drawing_no = data.drawing_no
    if getattr(data, "peer_contract_no", None) is not None:
        contract.peer_contract_no = data.peer_contract_no
    if getattr(data, "acquire_method", None) is not None:
        contract.acquire_method = data.acquire_method
    if getattr(data, "delivery_date", None) is not None:
        contract.delivery_date = _to_date(data.delivery_date)
    if getattr(data, "change_type", None) is not None:
        contract.change_type = data.change_type
    if getattr(data, "order_date", None) is not None:
        contract.order_date = _to_date(data.order_date)
    if getattr(data, "card_date", None) is not None:
        contract.card_date = _to_date(data.card_date)
    if getattr(data, "registration_json", None) is not None:
        contract.registration_json = data.registration_json
    if data.payment_terms_json is not None:
        contract.payment_terms_json = data.payment_terms_json
    if data.delivery_terms_json is not None:
        contract.delivery_terms_json = data.delivery_terms_json
    if data.custom_fields is not None:
        contract.custom_fields_json = data.custom_fields

    # 业务员 / 部门（名称可反查 ID；查不到仍保留名称字符串）
    raw_assignee_id = getattr(data, "assignee_id", None)
    raw_assignee_name = getattr(data, "assignee_name", None)
    if raw_assignee_id is not None or raw_assignee_name is not None:
        uid = await resolve_owner_id(
            db, tenant_id, owner_id=raw_assignee_id, owner_name=raw_assignee_name,
        )
        if uid:
            contract.assignee_id = uid
        elif raw_assignee_id is not None:
            contract.assignee_id = None
        if raw_assignee_name is not None:
            contract.assignee_name = (raw_assignee_name or "").strip() or None
        elif uid:
            from app.domains.auth.models import User as AuthUser
            u = (await db.execute(
                select(AuthUser).where(AuthUser.id == uid, AuthUser.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if u:
                contract.assignee_name = u.real_name or u.username

    raw_dept_id = getattr(data, "department_id", None)
    raw_dept_name = getattr(data, "department_name", None)
    if raw_dept_id is not None or raw_dept_name is not None:
        did = await resolve_department_id(
            db, tenant_id, department_id=raw_dept_id, department_name=raw_dept_name,
        )
        if did:
            contract.department_id = did
        elif raw_dept_id is not None:
            contract.department_id = None
        if raw_dept_name is not None:
            contract.department_name = (raw_dept_name or "").strip() or None
        elif did:
            from app.domains.organization.models import Department
            d = (await db.execute(
                select(Department).where(Department.id == did, Department.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if d:
                contract.department_name = d.name


async def _update_contract_version_from_openapi(
    db: AsyncSession, tenant_id: str, contract: Contract, data,
) -> None:
    """Update current version title and optional key_clauses from OpenAPI intake."""
    version = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id == contract.id,
            ContractVersion.version_no == contract.current_version_no,
        ).limit(1)
    )).scalar_one_or_none()
    if not version:
        return
    if data.title:
        version.title = data.title
    if getattr(data, "key_clauses_json", None) is not None:
        version.key_clauses_json = data.key_clauses_json


async def _update_contract_version_title(
    db: AsyncSession, tenant_id: str, contract: Contract, title: str | None,
) -> None:
    if not title:
        return
    version = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id == contract.id,
            ContractVersion.version_no == contract.current_version_no,
        ).limit(1)
    )).scalar_one_or_none()
    if version:
        version.title = title


async def update_contract_from_openapi(db: AsyncSession, ctx, contract: Contract, data) -> dict:
    """Update an existing contract from OpenAPI intake fields (中间服务推送修改)."""
    from app.domains.audit.service import log_action
    from app.domains.openapi.dto import contract_to_dto

    await _apply_openapi_contract_fields(db, ctx.tenant_id, contract, data)
    await _update_contract_version_from_openapi(db, ctx.tenant_id, contract, data)
    await db.commit()
    await db.refresh(contract)
    await log_action(
        db, tenant_id=ctx.tenant_id, user_id=ctx.app_id, user_name="开放平台",
        action="update", resource_type="contract", resource_id=contract.id,
        summary=f"开放平台更新合同: {contract.contract_no}",
    )
    return contract_to_dto(contract)


async def create_contract_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create or update a contract pushed by an external integrator (e.g. crm-integration).

    Customer-centric and project-optional. When ``contract_no`` already exists under
    the tenant this becomes an **upsert**. Requires Idempotency-Key at the router layer.
    """
    from app.common.code_generator import generate_code
    from app.domains.audit.service import log_action
    from app.domains.openapi.dto import contract_to_dto

    contract_no = data.contract_no or await generate_code(db, ctx.tenant_id, "contract")
    if data.contract_no:
        existing = (await db.execute(
            select(Contract).where(
                Contract.tenant_id == ctx.tenant_id,
                Contract.contract_no == data.contract_no,
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            return await update_contract_from_openapi(db, ctx, existing, data)

    contract = Contract(
        id=generate_uuid(), tenant_id=ctx.tenant_id,
        project_id=data.project_id,
        customer_id=data.customer_id,
        contract_no=contract_no,
        current_version_no=1,
        status=data.status or "draft",
        signed_date=_to_date(data.signed_date),
        end_date=_to_date(data.end_date),
        drawing_no=getattr(data, "drawing_no", None),
        peer_contract_no=getattr(data, "peer_contract_no", None),
        acquire_method=getattr(data, "acquire_method", None),
        delivery_date=_to_date(getattr(data, "delivery_date", None)),
        change_type=getattr(data, "change_type", None),
        order_date=_to_date(getattr(data, "order_date", None)),
        card_date=_to_date(getattr(data, "card_date", None)),
        amount_total=data.amount_total,
        payment_terms_json=data.payment_terms_json,
        delivery_terms_json=data.delivery_terms_json,
        registration_json=getattr(data, "registration_json", None),
        custom_fields_json=data.custom_fields or None,
        created_by_id=ctx.app_id, created_by_name="开放平台",
    )
    # Resolve assignee / department onto the new row before commit
    await _apply_openapi_contract_fields(db, ctx.tenant_id, contract, data)
    # customer_id / project_id already set; re-apply may overwrite from data — OK
    db.add(contract)

    version = ContractVersion(
        id=generate_uuid(), tenant_id=ctx.tenant_id,
        contract_id=contract.id, version_no=1,
        title=data.title or "V1",
        key_clauses_json=getattr(data, "key_clauses_json", None),
    )
    db.add(version)
    try:
        await db.commit()
    except IntegrityError:
        # Race: another writer inserted the same contract_no — upsert into that row.
        await db.rollback()
        existing = (await db.execute(
            select(Contract).where(
                Contract.tenant_id == ctx.tenant_id,
                Contract.contract_no == contract_no,
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            return await update_contract_from_openapi(db, ctx, existing, data)
        raise OpenApiException(
            CRM_DUPLICATE_ENTRY,
            f"合同编号 {contract_no} 已存在",
            http_status=409,
            details={"contract_no": contract_no},
        )
    await db.refresh(contract)

    await log_action(
        db, tenant_id=ctx.tenant_id, user_id=ctx.app_id, user_name="开放平台",
        action="create", resource_type="contract", resource_id=contract.id,
        summary=f"开放平台创建合同: {contract.contract_no}",
    )
    return contract_to_dto(contract)


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
