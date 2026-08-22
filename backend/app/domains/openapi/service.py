"""Open API service layer: app management, call logging, and read queries.

Read queries filter strictly by ``tenant_id`` (+ ``is_deleted == False`` where the
model has it) so an app can only ever see its own tenant's data. Results are handed
to the DTO layer before leaving the process.
"""
from __future__ import annotations

from datetime import datetime, timezone

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
    base = select(ServiceTicket).where(
        ServiceTicket.tenant_id == tenant_id, ServiceTicket.is_deleted == False,  # noqa: E712
    )
    if customer_id:
        base = base.where(ServiceTicket.customer_id == customer_id)
    if status:
        base = base.where(ServiceTicket.status == status)
    dt = _parse_dt(updated_since)
    if dt:
        base = base.where(ServiceTicket.updated_at >= dt)
    return await _paginate(db, base, ServiceTicket.updated_at, page, page_size)


async def get_service_ticket(db, tenant_id, obj_id):
    row = await _get_one(db, ServiceTicket, tenant_id, obj_id)
    if row is not None and getattr(row, "is_deleted", False):
        return None
    return row


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


async def resolve_created_by(
    db: AsyncSession, tenant_id: str, *, created_by_id: str | None, created_by_name: str | None,
) -> tuple[str | None, str | None]:
    """Resolve 填表人 → (user_id, display_name).

    Name is kept even when CRM has no matching user, so UI shows 简道云填表人
    instead of「开放平台」.
    """
    from app.domains.auth.models import User as AuthUser

    name = (created_by_name or "").strip() or None
    uid = await resolve_user_id(
        db, tenant_id, user_id=created_by_id, user_name=name, field_label="created_by",
    )
    if uid:
        u = (await db.execute(
            select(AuthUser).where(AuthUser.id == uid, AuthUser.tenant_id == tenant_id)
        )).scalar_one_or_none()
        display = (u.real_name or u.username) if u else name
        return uid, display or name
    return None, name


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


_CATEGORY_ALIASES = {
    "自报": "self_reported",
    "分发": "distributed",
    "self_reported": "self_reported",
    "distributed": "distributed",
}
_COUNTRY_TYPE_ALIASES = {
    "国内": "domestic",
    "国外": "overseas",
    "domestic": "domestic",
    "overseas": "overseas",
}
_NEWNESS_ALIASES = {
    "新": "new",
    "老": "old",
    "新客户": "new",
    "老客户": "old",
    "new": "new",
    "old": "old",
}


def _normalize_alias(raw: str | None, aliases: dict[str, str]) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return aliases.get(text) or aliases.get(text.replace(" ", ""))


async def _resolve_lead_write_payload(db: AsyncSession, ctx, data) -> dict:
    """Shared open-API lead field resolution (dept / owner / reporter names → ids)."""
    payload = data.model_dump(exclude_unset=True)
    # Keep pydantic step objects for import_lead_flow_history (model_dump would nest dicts).
    if getattr(data, "flow_history", None) is not None:
        payload["flow_history"] = list(data.flow_history)
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

    # 填表人：不进 LeadCreate（由 create_lead 伪用户占位），解析后单独回写。
    filler_name = payload.pop("created_by_name", None)
    raw_filler_id = payload.pop("created_by_id", None)
    filler_id, filler_display = await resolve_created_by(
        db, ctx.tenant_id, created_by_id=raw_filler_id, created_by_name=filler_name,
    )
    if filler_id or filler_display:
        payload["_filler_id"] = filler_id
        payload["_filler_name"] = filler_display

    if "lead_code" in payload:
        code = (payload.get("lead_code") or "").strip()
        if code:
            payload["lead_code"] = code[:64]
        else:
            payload.pop("lead_code", None)

    if "customer_type" in payload:
        payload["customer_type"] = await resolve_customer_type(
            db, ctx.tenant_id, payload.get("customer_type"),
        )
    if "category" in payload:
        payload["category"] = _normalize_alias(payload.get("category"), _CATEGORY_ALIASES)
        if payload.get("category") is None:
            payload.pop("category", None)
    if "country_type" in payload:
        payload["country_type"] = _normalize_alias(payload.get("country_type"), _COUNTRY_TYPE_ALIASES)
        if payload.get("country_type") is None:
            payload.pop("country_type", None)
        if payload.get("country_type") != "overseas":
            payload["country_name"] = None
    if "customer_newness" in payload:
        payload["customer_newness"] = _normalize_alias(
            payload.get("customer_newness"), _NEWNESS_ALIASES,
        )
        if payload.get("customer_newness") is None:
            payload.pop("customer_newness", None)
    # 项目编号误写入「其他备注」时清掉（历史映射）
    code = (payload.get("lead_code") or "").strip()
    remark = payload.get("remark")
    if code and isinstance(remark, str) and remark.strip() == code:
        payload["remark"] = None
    elif code and "remark" not in payload:
        # 幂等补全项目号时，若库里备注仍是项目号，下面 update 路径再处理
        pass
    if "reject_reason" in payload:
        rr = (payload.get("reject_reason") or "").strip()
        if rr:
            payload["reject_reason"] = rr
        else:
            payload.pop("reject_reason", None)
    # 地址：有省市区但未传 region 时拼接（对齐客户 OpenAPI）
    if not payload.get("region"):
        parts = [payload.get("province"), payload.get("city"), payload.get("district")]
        joined = "".join(p for p in parts if p)
        if joined:
            payload["region"] = joined
    # 系统时间字段不进 LeadCreate/LeadUpdate；末尾由 _apply_pushed_timestamps 覆盖。
    created_at = payload.pop("created_at", None)
    updated_at = payload.pop("updated_at", None)
    if created_at is not None:
        payload["_created_at"] = created_at
    if updated_at is not None:
        payload["_updated_at"] = updated_at
    return payload


async def _apply_pushed_timestamps(db: AsyncSession, entity, payload: dict) -> bool:
    """用推送的 created_at/updated_at 覆盖 CRM 系统时间（有值才写）。"""
    created_at = payload.pop("_created_at", None)
    updated_at = payload.pop("_updated_at", None)
    if created_at is None and updated_at is None:
        return False
    changed = False
    if created_at is not None and getattr(entity, "created_at", None) != created_at:
        entity.created_at = created_at
        changed = True
    if updated_at is not None and getattr(entity, "updated_at", None) != updated_at:
        entity.updated_at = updated_at
        changed = True
    if changed:
        await db.commit()
        await db.refresh(entity)
    return changed


# 简道云「项目最终状态」→ CRM review_status
_REVIEW_STATUS_ALIASES = {
    "收录": "approved",
    "袭击": "attacked",
    "回退": "rejected",
    "待审": "draft",
    "approved": "approved",
    "attacked": "attacked",
    "rejected": "rejected",
    "draft": "draft",
}
_EXTERNAL_REVIEWED = frozenset({"approved", "attacked", "rejected"})

# 简道云 finishAction / 按钮文案 → CRM WfTaskActionLog.action
_FLOW_ACTION_ALIASES = {
    "forward": "approve",
    "submit": "submit",
    "reject": "reject",
    "back": "reject",
    "return": "return",
    "cc": "comment",
    "auto": "auto_approve",
    "提交": "submit",
    "发起": "submit",
    "通过": "approve",
    "同意": "approve",
    "收录": "approve",
    "袭击": "approve",
    "收录/袭击": "approve",
    "驳回": "reject",
    "回退": "reject",
    "approve": "approve",
    "approved": "approve",
}
_JDY_IMPORT_BIZ_NO = "jdy-import"


def normalize_review_status(raw: str | None) -> str | None:
    """Map JianDaoYun 项目最终状态 / English code → CRM review_status."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return _REVIEW_STATUS_ALIASES.get(text) or _REVIEW_STATUS_ALIASES.get(text.replace(" ", ""))


def _normalize_flow_action(raw: str | None) -> str:
    if not raw:
        return "approve"
    text = str(raw).strip()
    if not text:
        return "approve"
    mapped = _FLOW_ACTION_ALIASES.get(text) or _FLOW_ACTION_ALIASES.get(text.lower())
    if mapped:
        return mapped
    # 「收录/袭击」等复合文案
    for key, val in _FLOW_ACTION_ALIASES.items():
        if key in text:
            return val
    return "approve"


def _flow_step_get(step, key: str, default=None):
    """Accept OpenFlowHistoryStep or plain dict (idempotent update path)."""
    if isinstance(step, dict):
        return step.get(key, default)
    return getattr(step, key, default)


async def _delete_wf_instance_tree(db: AsyncSession, tenant_id: str, instance_id: str) -> None:
    from app.domains.lowcode.workflow_models import (
        WfProcessInstance, WfNodeInstance, WfTaskInstance,
        WfTaskActionLog, WfProcessComment, WfProcessCc,
    )
    for model in (WfTaskActionLog, WfProcessComment, WfProcessCc, WfTaskInstance, WfNodeInstance):
        rows = (await db.execute(select(model).where(
            model.process_instance_id == instance_id,
            model.tenant_id == tenant_id,
        ))).scalars().all()
        for row in rows:
            await db.delete(row)
    inst = await db.get(WfProcessInstance, instance_id)
    if inst and inst.tenant_id == tenant_id:
        await db.delete(inst)


async def import_lead_flow_history(db: AsyncSession, ctx, lead, steps) -> str | None:
    """把简道云流程动态落成已结束的 CRM 流程实例，供线索详情「流程动态」展示。"""
    from app.domains.lead.service import LEAD_DEFAULT_FLOW_CODE
    from app.domains.lowcode.workflow_service import _lead_intel_approver_rule

    title = f"简道云流程: {(lead.lead_code + ' ') if lead.lead_code else ''}{lead.title}"
    initiator_id = lead.reporter_id or lead.owner_id or ctx.app_id
    inst_id = await _import_jdy_flow_history(
        db, ctx,
        biz_type="lead",
        biz_id=lead.id,
        title=title,
        flow_code=LEAD_DEFAULT_FLOW_CODE,
        flow_name="信息情报部审批",
        initiator_id=initiator_id,
        department_id=lead.department_id,
        steps=steps,
        approver_rule=_lead_intel_approver_rule(),
    )
    if inst_id:
        lead.review_flow_id = inst_id
        await db.commit()
        await db.refresh(lead)
    return inst_id


async def import_customer_flow_history(db: AsyncSession, ctx, customer, steps) -> str | None:
    """把简道云客户信息流程动态落成已结束实例，供客户详情「流程动态」展示。"""
    from app.domains.customer.service import CUSTOMER_DEFAULT_FLOW_CODE

    code = getattr(customer, "customer_code", None) or ""
    title = f"简道云流程: {(code + ' ') if code else ''}{customer.name}"
    initiator_id = customer.owner_id or customer.created_by_id or ctx.app_id
    inst_id = await _import_jdy_flow_history(
        db, ctx,
        biz_type="customer",
        biz_id=customer.id,
        title=title,
        flow_code=CUSTOMER_DEFAULT_FLOW_CODE,
        flow_name="客户信息审批",
        initiator_id=initiator_id,
        department_id=customer.department_id,
        steps=steps,
        approver_rule={
            "type": "specified_user", "value": "03303022525221387032", "exclude_initiator": True,
        },
    )
    if inst_id:
        customer.review_flow_id = inst_id
        await db.commit()
        await db.refresh(customer)
    return inst_id


async def _import_jdy_flow_history(
    db: AsyncSession, ctx, *,
    biz_type: str,
    biz_id: str,
    title: str,
    flow_code: str,
    flow_name: str,
    initiator_id: str | None,
    department_id: str | None,
    steps,
    approver_rule: dict | None = None,
    flow_finished: bool | None = None,
) -> str | None:
    """Shared JianDaoYun → CRM WF import (lead / customer / contract_version).

    ``flow_finished``:
      - True / None → 已结束（rejected 或 completed；None 兼容历史调用）
      - False → 进行中（status=running，供合同列表「审批中」）
    """
    if not steps:
        return None
    from app.domains.auth.models import User
    from app.domains.lowcode.workflow_models import (
        WfProcessDefinition, WfProcessInstance, WfNodeInstance,
        WfTaskInstance, WfTaskActionLog,
    )
    from app.domains.lowcode.workflow_service import (
        ensure_default_definition, _published_version,
    )
    from app.database import utcnow

    rule = approver_rule or {
        "type": "specified_role", "value": "admin", "exclude_initiator": True,
    }
    await ensure_default_definition(
        db, ctx.tenant_id, biz_type=biz_type, code=flow_code, name=flow_name,
        approver_rule=rule,
        multi_mode="or_sign", empty_strategy="auto_approve",
    )
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == ctx.tenant_id,
        WfProcessDefinition.biz_type == biz_type,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).order_by(
        WfProcessDefinition.sort_order.asc(), WfProcessDefinition.created_at.asc()
    ).limit(1))).scalar_one_or_none()
    if not d:
        return None
    version = await _published_version(db, ctx.tenant_id, d.id)
    if not version:
        return None

    olds = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.tenant_id == ctx.tenant_id,
        WfProcessInstance.biz_type == biz_type,
        WfProcessInstance.biz_id == biz_id,
        WfProcessInstance.business_no == _JDY_IMPORT_BIZ_NO,
    ))).scalars().all()
    for old in olds:
        await _delete_wf_instance_tree(db, ctx.tenant_id, old.id)

    name_cache: dict[str, str] = {}

    async def resolve_actor(name: str | None) -> tuple[str, str | None]:
        display = (name or "").strip() or None
        if not display:
            return ctx.app_id, None
        if display in name_cache:
            return name_cache[display], display
        u = (await db.execute(select(User).where(
            User.tenant_id == ctx.tenant_id,
            User.is_active == True,  # noqa: E712
            or_(User.real_name == display, User.username == display),
        ).limit(1))).scalar_one_or_none()
        uid = u.id if u else ctx.app_id
        name_cache[display] = uid
        return uid, display

    _epoch = datetime.min.replace(tzinfo=timezone.utc)

    def _step_key(s):
        t = _flow_step_get(s, "started_at") or _flow_step_get(s, "completed_at")
        if t is None:
            return _epoch
        if getattr(t, "tzinfo", None) is None:
            return t.replace(tzinfo=timezone.utc)
        return t

    ordered = sorted(steps, key=_step_key)
    has_reject = False
    times = []
    for s in ordered:
        if _flow_step_get(s, "started_at"):
            times.append(_flow_step_get(s, "started_at"))
        if _flow_step_get(s, "completed_at"):
            times.append(_flow_step_get(s, "completed_at"))
        act = _normalize_flow_action(_flow_step_get(s, "action"))
        if act in ("reject", "auto_reject", "return"):
            has_reject = True

    started_at = min(times) if times else utcnow()
    finished = True if flow_finished is None else bool(flow_finished)
    if has_reject:
        flow_status = "rejected"
        completed_at = max(times) if times else utcnow()
    elif finished:
        flow_status = "completed"
        completed_at = max(times) if times else utcnow()
    else:
        flow_status = "running"
        completed_at = None

    inst = WfProcessInstance(
        id=generate_uuid(),
        tenant_id=ctx.tenant_id,
        process_definition_id=d.id,
        process_version_id=version.id,
        biz_type=biz_type,
        biz_id=biz_id,
        business_no=_JDY_IMPORT_BIZ_NO,
        title=title[:200],
        initiator_id=initiator_id or ctx.app_id,
        initiator_dept_id=department_id,
        status=flow_status,
        started_at=started_at,
        completed_at=completed_at,
        is_test=False,
    )
    db.add(inst)
    await db.flush()

    for idx, step in enumerate(ordered):
        node_name = (_flow_step_get(step, "node_name") or "").strip() or f"节点{idx + 1}"
        action = _normalize_flow_action(_flow_step_get(step, "action"))
        opinion = (_flow_step_get(step, "opinion") or "").strip() or None
        raw_action = (_flow_step_get(step, "action") or "").strip()
        if raw_action and raw_action not in _FLOW_ACTION_ALIASES and action == "approve":
            opinion = f"{raw_action}" + (f"；{opinion}" if opinion else "")
        node_status = "rejected" if action in ("reject", "auto_reject", "return") else "completed"
        node_type = "start" if idx == 0 and ("递呈" in node_name or "发起" in node_name) else "approval"
        handler_name = _flow_step_get(step, "handler_name")
        actor_id, actor_name = await resolve_actor(handler_name)
        n_started = _flow_step_get(step, "started_at") or _flow_step_get(step, "completed_at") or started_at
        n_completed = _flow_step_get(step, "completed_at") or _flow_step_get(step, "started_at") or n_started

        node = WfNodeInstance(
            id=generate_uuid(),
            tenant_id=ctx.tenant_id,
            process_instance_id=inst.id,
            node_def_id=f"jdy_import_{idx}",
            node_type=node_type,
            node_name=node_name[:128],
            status=node_status,
            config={},
            started_at=n_started,
            completed_at=n_completed,
        )
        db.add(node)
        await db.flush()

        task = WfTaskInstance(
            id=generate_uuid(),
            tenant_id=ctx.tenant_id,
            process_instance_id=inst.id,
            node_instance_id=node.id,
            assignee_id=actor_id,
            status=node_status,
            opinion=opinion,
            action_at=n_completed,
            version=1,
            task_order=0,
        )
        db.add(task)
        await db.flush()

        log_action = action
        if node_type == "start" and action == "approve":
            log_action = "submit"
        db.add(WfTaskActionLog(
            id=generate_uuid(),
            tenant_id=ctx.tenant_id,
            process_instance_id=inst.id,
            node_instance_id=node.id,
            task_instance_id=task.id,
            actor_id=actor_id,
            actor_name=actor_name or handler_name,
            action=log_action,
            opinion=opinion,
            extra={"source": "jdy", "raw_action": raw_action or None},
        ))

    await db.flush()
    return inst.id


async def import_contract_version_flow_history(
    db: AsyncSession, ctx, version: ContractVersion, contract: Contract, steps,
    flow_finished: bool | None = None,
) -> str | None:
    """Import JianDaoYun 合同登记流程 onto the current contract_version."""
    if not steps:
        return None
    title = f"{contract.contract_no or ''} {version.title or ''}".strip() or "合同登记"
    return await _import_jdy_flow_history(
        db, ctx,
        biz_type="contract_version",
        biz_id=version.id,
        title=title,
        flow_code="contract_version_approval",
        flow_name="合同版本审批",
        initiator_id=contract.created_by_id or ctx.app_id,
        department_id=contract.department_id,
        steps=steps,
        flow_finished=flow_finished,
    )


async def create_lead_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create a lead from an external app. Reuses the internal lead service so all
    business rules (code generation, scoring, audit) apply.

    If ``owner_id`` / ``owner_name`` resolve to a CRM user, the lead is assigned to
    that user (简道云「申报人」→ CRM 负责人). Otherwise it is left in the open pool.
    ``reporter_*`` maps the same JianDaoYun申报人 onto CRM 报备人 when provided.

    ``review_status``：简道云已审（收录/袭击/回退）时免 CRM 内审直接落终态；
    待审/未传仍落草稿，便于幂等补全。
    """
    from app.domains.lead.service import create_lead
    from app.domains.lead.schemas import LeadCreate
    from app.domains.openapi.dto import lead_to_dto

    payload = await _resolve_lead_write_payload(db, ctx, data)
    flow_history = payload.pop("flow_history", None) or getattr(data, "flow_history", None)
    review_status = normalize_review_status(payload.pop("review_status", None))
    externally_reviewed = review_status in _EXTERNAL_REVIEWED
    filler_id = payload.pop("_filler_id", None)
    filler_name = payload.pop("_filler_name", None)
    pushed_ts = {
        k: payload.pop(k) for k in ("_created_at", "_updated_at") if k in payload
    }

    if externally_reviewed:
        # 免启 CRM 情报审；模型默认 approved，袭击/回退再覆盖
        lead = await create_lead(
            db, ctx.tenant_id,
            LeadCreate(**{**payload, "as_draft": False}),
            _pseudo_user(ctx),
            auto_review=False,
            external_origin="jdy",
        )
        if review_status != "approved":
            lead.review_status = review_status
        if review_status in ("approved", "attacked"):
            from app.domains.lead.reactivation import mark_cycle_reset
            mark_cycle_reset(lead)
        await db.commit()
        await db.refresh(lead)
    else:
        lead = await create_lead(
            db, ctx.tenant_id,
            LeadCreate(**{**payload, "as_draft": True}),
            _pseudo_user(ctx),
            external_origin="jdy",
        )
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
    # 填表人：覆盖开放平台伪创建人
    if filler_id or filler_name:
        lead.created_by_id = filler_id
        lead.created_by_name = filler_name
        await db.commit()
        await db.refresh(lead)
    if flow_history:
        await import_lead_flow_history(db, ctx, lead, flow_history)
    # 历史误把项目编号写入 remark：与 lead_code 相同时清掉
    if (
        getattr(lead, "remark", None)
        and getattr(lead, "lead_code", None)
        and str(lead.remark).strip() == str(lead.lead_code).strip()
    ):
        lead.remark = None
        await db.commit()
        await db.refresh(lead)
    await _apply_pushed_timestamps(db, lead, pushed_ts)
    return lead_to_dto(lead)


async def update_lead_from_openapi(db: AsyncSession, ctx, lead_id: str, data) -> dict:
    """Update an existing open-API lead (e.g. idempotent replay with a richer body).

    Only resolved department / owner / reporter ids and reported_at (plus other
    provided scalar fields) are written; unresolved names do not clear existing
    assignments.

    ``review_status``：仅允许从 draft 晋升为外部终态（收录/袭击/回退）；
    不降级、不动 pending（尊重 CRM 内审）。
    """
    from app.domains.lead.service import update_lead
    from app.domains.lead.schemas import LeadUpdate
    from app.domains.openapi.dto import lead_to_dto

    payload = await _resolve_lead_write_payload(db, ctx, data)
    flow_history = payload.pop("flow_history", None) or getattr(data, "flow_history", None)
    review_status = normalize_review_status(payload.pop("review_status", None))
    filler_id = payload.pop("_filler_id", None)
    filler_name = payload.pop("_filler_name", None)
    pushed_ts = {
        k: payload.pop(k) for k in ("_created_at", "_updated_at") if k in payload
    }
    # Don't blank owner/dept when name resolution fails on a backfill replay.
    for k in ("department_id", "owner_id", "reporter_id"):
        if k in payload and not payload[k]:
            payload.pop(k)
    lead = await update_lead(db, ctx.tenant_id, lead_id, LeadUpdate(**payload), _pseudo_user(ctx))
    if review_status in _EXTERNAL_REVIEWED and getattr(lead, "review_status", None) == "draft":
        lead.review_status = review_status
        if review_status in ("approved", "attacked"):
            from app.domains.lead.reactivation import mark_cycle_reset
            mark_cycle_reset(lead)
        await db.commit()
        await db.refresh(lead)
    # 幂等补全填表人：覆盖开放平台占位，或写入此前缺失的填表人
    if filler_id or filler_name:
        cur = getattr(lead, "created_by_id", None)
        if (not cur) or cur == ctx.app_id or filler_id:
            lead.created_by_id = filler_id or (None if cur == ctx.app_id else cur)
            lead.created_by_name = filler_name or lead.created_by_name
            await db.commit()
            await db.refresh(lead)
    if flow_history:
        await import_lead_flow_history(db, ctx, lead, flow_history)
    if (
        getattr(lead, "remark", None)
        and getattr(lead, "lead_code", None)
        and str(lead.remark).strip() == str(lead.lead_code).strip()
    ):
        lead.remark = None
        await db.commit()
        await db.refresh(lead)
    await _apply_pushed_timestamps(db, lead, pushed_ts)
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


def _coerce_bool_cn(v) -> bool | None:
    """Normalize 是/否 / true/false / 1/0 into bool; empty → None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    text = str(v).strip().lower()
    if not text:
        return None
    if text in ("是", "true", "1", "yes", "y"):
        return True
    if text in ("否", "false", "0", "no", "n"):
        return False
    return None


def _coerce_float(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    text = str(v).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    text = str(v).strip()
    if not text:
        return None
    # 成立年份常为 ISO datetime（简道云 datetime 控件）
    if len(text) >= 4 and text[:4].isdigit() and (len(text) == 4 or text[4] in "-T /"):
        try:
            return int(text[:4])
        except ValueError:
            pass
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def _coerce_main_products(v) -> list | None:
    if v is None or v == "":
        return None
    if isinstance(v, list):
        return v
    text = str(v).strip()
    if not text:
        return None
    if text.startswith("["):
        import json
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    # checkbox flatten: "A, B, C"
    parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
    return parts or None


async def _resolve_customer_write_payload(db: AsyncSession, ctx, data) -> dict:
    """Normalize open-API customer fields; resolve owner/dept names → ids."""
    payload = data.model_dump(exclude_unset=True)
    # Keep pydantic step objects for import_customer_flow_history.
    if getattr(data, "flow_history", None) is not None:
        payload["flow_history"] = list(data.flow_history)

    dept_name = payload.pop("department_name", None)
    raw_dept_id = payload.pop("department_id", None)
    resolved_dept = await resolve_department_id(
        db, ctx.tenant_id, department_id=raw_dept_id, department_name=dept_name,
    )
    if resolved_dept:
        payload["_department_id"] = resolved_dept
    if dept_name and str(dept_name).strip():
        payload["_department_name"] = str(dept_name).strip()

    owner_name = payload.pop("owner_name", None)
    raw_owner_id = payload.pop("owner_id", None)
    resolved_owner = await resolve_owner_id(
        db, ctx.tenant_id, owner_id=raw_owner_id, owner_name=owner_name,
    )
    if resolved_owner:
        payload["owner_id"] = resolved_owner

    if "customer_code" in payload:
        code = (payload.get("customer_code") or "").strip()
        if code:
            payload["customer_code"] = code[:100]
        else:
            payload.pop("customer_code", None)

    for key in (
        "is_smart_filing", "is_foreign_trade", "is_company_customer",
        "need_info_distribute", "as_draft",
    ):
        if key in payload:
            coerced = _coerce_bool_cn(payload.get(key))
            if coerced is None and key == "as_draft":
                payload[key] = True  # openapi 默认免启 CRM 内审
            elif coerced is None:
                payload.pop(key, None)
            else:
                payload[key] = coerced

    for key in ("registered_capital", "paid_in_capital"):
        if key in payload:
            coerced = _coerce_float(payload.get(key))
            if coerced is None:
                payload.pop(key, None)
            else:
                payload[key] = coerced

    if "founded_year" in payload:
        year = _coerce_int(payload.get("founded_year"))
        if year is None or year < 1800 or year > 2100:
            payload.pop("founded_year", None)
        else:
            payload["founded_year"] = year

    if "headcount" in payload:
        hc = _coerce_int(payload.get("headcount"))
        if hc is None:
            payload.pop("headcount", None)
        else:
            payload["headcount"] = hc

    if "main_products_json" in payload:
        products = _coerce_main_products(payload.get("main_products_json"))
        if products is None:
            payload.pop("main_products_json", None)
        else:
            payload["main_products_json"] = products

    # region 兜底：有省市区但未传 region 时拼接
    if not payload.get("region"):
        parts = [payload.get("province"), payload.get("city"), payload.get("district")]
        joined = "".join(p for p in parts if p)
        if joined:
            payload["region"] = joined

    # 系统时间不进 CustomerCreate/Update；末尾 _apply_pushed_timestamps 覆盖。
    created_at = payload.pop("created_at", None)
    updated_at = payload.pop("updated_at", None)
    if created_at is not None:
        payload["_created_at"] = created_at
    if updated_at is not None:
        payload["_updated_at"] = updated_at

    return payload


async def _apply_customer_department(customer, payload: dict) -> bool:
    """Write explicit 业务部门 when resolved; returns whether mutated."""
    dept_id = payload.pop("_department_id", None)
    dept_name = payload.pop("_department_name", None)
    changed = False
    if dept_id and customer.department_id != dept_id:
        customer.department_id = dept_id
        changed = True
    if dept_name and customer.department_name != dept_name:
        customer.department_name = dept_name
        changed = True
    return changed


async def _find_customer_by_code(db: AsyncSession, tenant_id: str, customer_code: str):
    from app.domains.customer.models import Customer
    return (await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.customer_code == customer_code,
            Customer.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def create_customer_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create or upsert a customer via the internal service.

    When ``customer_code`` is non-empty and already exists for the tenant, update
    that row instead of inserting a duplicate (简道云客户编号 sn).

    默认 ``as_draft=True``：不启 CRM「客户信息审批」（简道云侧已审）；导入
    ``flow_history`` 后落成已结束流程并标 ``review_status=approved``。
    """
    from app.domains.customer.service import create_customer
    from app.domains.customer.schemas import CustomerCreate
    from app.domains.openapi.dto import customer_to_dto

    payload = await _resolve_customer_write_payload(db, ctx, data)
    flow_history = payload.pop("flow_history", None) or getattr(data, "flow_history", None)
    code = (payload.get("customer_code") or "").strip()
    if code:
        existing = await _find_customer_by_code(db, ctx.tenant_id, code)
        if existing:
            return await update_customer_from_openapi(db, ctx, existing.id, data)

    dept_id = payload.pop("_department_id", None)
    dept_name = payload.pop("_department_name", None)
    pushed_ts = {
        k: payload.pop(k) for k in ("_created_at", "_updated_at") if k in payload
    }
    # 开放平台默认免启 CRM 内审；仅显式 as_draft=false 才走待审提交
    if "as_draft" not in payload:
        payload["as_draft"] = True
    customer = await create_customer(
        db, ctx.tenant_id, CustomerCreate(**payload), _pseudo_user(ctx),
    )
    if customer.owner_id == ctx.app_id:
        customer.owner_id = None
        customer.owner_name = "开放平台（待分配）"
        await db.commit()
        await db.refresh(customer)
    if dept_id or dept_name:
        if await _apply_customer_department(
            customer, {"_department_id": dept_id, "_department_name": dept_name},
        ):
            await db.commit()
            await db.refresh(customer)
    if flow_history:
        await import_customer_flow_history(db, ctx, customer, flow_history)
    # 简道云同步进来的客户视为已审（除非仍在 CRM pending 且未带流程）
    if payload.get("as_draft", True) and getattr(customer, "review_status", None) in (
        None, "draft", "pending",
    ):
        customer.review_status = "approved"
        await db.commit()
        await db.refresh(customer)
    await _apply_pushed_timestamps(db, customer, pushed_ts)
    return customer_to_dto(customer)


async def update_customer_from_openapi(db: AsyncSession, ctx, customer_id: str, data) -> dict:
    """Update an existing open-API customer (idempotent replay / code upsert)."""
    from app.domains.customer.service import update_customer
    from app.domains.customer.schemas import CustomerUpdate
    from app.domains.openapi.dto import customer_to_dto

    payload = await _resolve_customer_write_payload(db, ctx, data)
    flow_history = payload.pop("flow_history", None) or getattr(data, "flow_history", None)
    payload.pop("as_draft", None)  # CustomerUpdate 无 as_draft
    dept_id = payload.pop("_department_id", None)
    dept_name = payload.pop("_department_name", None)
    pushed_ts = {
        k: payload.pop(k) for k in ("_created_at", "_updated_at") if k in payload
    }
    # Don't blank owner when name resolution fails on a backfill replay.
    if "owner_id" in payload and not payload["owner_id"]:
        payload.pop("owner_id")
    customer = await update_customer(
        db, ctx.tenant_id, customer_id, CustomerUpdate(**payload), _pseudo_user(ctx),
    )
    if dept_id or dept_name:
        if await _apply_customer_department(
            customer, {"_department_id": dept_id, "_department_name": dept_name},
        ):
            await db.commit()
            await db.refresh(customer)
    if flow_history:
        await import_customer_flow_history(db, ctx, customer, flow_history)
    if getattr(customer, "review_status", None) in (None, "draft", "pending"):
        customer.review_status = "approved"
        await db.commit()
        await db.refresh(customer)
    await _apply_pushed_timestamps(db, customer, pushed_ts)
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
) -> ContractVersion | None:
    """Update current version title / key_clauses / version_status from OpenAPI intake."""
    version = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id == contract.id,
            ContractVersion.version_no == contract.current_version_no,
        ).limit(1)
    )).scalar_one_or_none()
    if not version:
        return None
    if data.title:
        version.title = data.title
    if getattr(data, "key_clauses_json", None) is not None:
        version.key_clauses_json = data.key_clauses_json
    vs = getattr(data, "version_status", None)
    if vs:
        version.status = vs
    return version


async def _apply_contract_flow_from_openapi(
    db: AsyncSession, ctx, contract: Contract, version: ContractVersion | None, data,
) -> None:
    """Import JianDaoYun flow_history onto contract_version when provided."""
    steps = getattr(data, "flow_history", None)
    if not steps or version is None:
        return
    # Keep pydantic step objects for import (same as lead/customer).
    await import_contract_version_flow_history(
        db, ctx, version, contract, list(steps),
        flow_finished=getattr(data, "flow_finished", None),
    )


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
    version = await _update_contract_version_from_openapi(db, ctx.tenant_id, contract, data)
    await _apply_contract_flow_from_openapi(db, ctx, contract, version, data)
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

    from app.domains.contract.service import (
        _resolve_create_drawing_no,
        allocate_create_drawing_no,
        drawing_no_apply_date_today,
    )
    reg = getattr(data, "registration_json", None) or {}
    if not isinstance(reg, dict):
        reg = {}
    openapi_user = {"sub": ctx.app_id, "real_name": "开放平台", "username": "openapi"}
    requested_dn = (getattr(data, "drawing_no", None) or "").strip() or None
    if requested_dn:
        # 有传入号：直接采用并校验唯一（不强制对应表存在）
        drawing_no = await _resolve_create_drawing_no(
            db, ctx.tenant_id, openapi_user, requested_dn,
            apply_date=drawing_no_apply_date_today(),
            trust_requested=True,
            map_contract_no=contract_no if data.contract_no else None,
        )
    else:
        # 无显式图纸号：按取号当天自动生成（兼容中间服务推送）
        drawing_no = await allocate_create_drawing_no(
            db, ctx.tenant_id, openapi_user,
            apply_date=drawing_no_apply_date_today(),
        )

    contract = Contract(
        id=generate_uuid(), tenant_id=ctx.tenant_id,
        project_id=data.project_id,
        customer_id=data.customer_id,
        contract_no=contract_no,
        current_version_no=1,
        status=data.status or "draft",
        signed_date=_to_date(data.signed_date),
        end_date=_to_date(data.end_date),
        drawing_no=drawing_no,
        peer_contract_no=getattr(data, "peer_contract_no", None),
        acquire_method=getattr(data, "acquire_method", None),
        delivery_date=_to_date(getattr(data, "delivery_date", None)),
        change_type=getattr(data, "change_type", None),
        order_date=_to_date(getattr(data, "order_date", None)),
        card_date=_to_date(getattr(data, "card_date", None)),
        amount_total=data.amount_total,
        payment_terms_json=data.payment_terms_json,
        delivery_terms_json=data.delivery_terms_json,
        registration_json=reg or None,
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
        status=getattr(data, "version_status", None) or "draft",
    )
    db.add(version)
    await _apply_contract_flow_from_openapi(db, ctx, contract, version, data)
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


# ============================================================ writes (low-code forms)
_OPENAPI_FORM_CODES = frozenset({
    "drawing_requisition",
    "install_drawing_notice",
    "prod_card_supplement",
})
_FILE_FIELD_TYPES = frozenset({"file", "image"})


def _file_field_to_att_refs(val) -> list[dict]:
    """JianDaoYun file/image → CRM [{id,name}] refs until binary sync exists.

    Frontend FileField / list cells require {id, name}. Plain name strings are
    invisible (filtered by missing id). Use jdy-meta: prefix for name-only refs.
    """
    if val in (None, "", [], {}):
        return []
    if isinstance(val, str):
        s = val.strip()
        # JSON-encoded list from middleware as=json
        if s.startswith("[") or s.startswith("{"):
            try:
                import json as _json
                return _file_field_to_att_refs(_json.loads(s))
            except Exception:
                pass
        return [{"id": f"jdy-meta:{s}", "name": s, "metaOnly": True}] if s else []
    items = val if isinstance(val, list) else [val]
    refs: list[dict] = []
    seen: set[str] = set()
    for it in items:
        name = ""
        if isinstance(it, str):
            name = it.strip()
        elif isinstance(it, dict):
            # already normalized
            existing_id = it.get("id")
            existing_name = it.get("name") or it.get("fileName") or it.get("filename")
            if existing_id and existing_name and str(existing_id).startswith("jdy-meta:"):
                key = str(existing_name)
                if key not in seen:
                    seen.add(key)
                    refs.append({
                        "id": str(existing_id),
                        "name": str(existing_name),
                        "metaOnly": True,
                    })
                continue
            name = str(existing_name or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        refs.append({"id": f"jdy-meta:{name}", "name": name, "metaOnly": True})
    return refs


async def _normalize_openapi_form_data(
    db: AsyncSession, tenant_id: str, field_defs: list, form_data: dict,
) -> dict:
    """Resolve person/department names → UUIDs; keep file fields as name-only refs (no binary)."""
    out = dict(form_data or {})
    for fd in field_defs or []:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        if not fid or fid not in out:
            continue
        ftype = fd.get("type") or ""
        if ftype in _FILE_FIELD_TYPES:
            out[fid] = _file_field_to_att_refs(out.get(fid))
            if not out[fid]:
                out.pop(fid, None)
            continue
        val = out.get(fid)
        if val in (None, "", [], {}):
            continue
        # auto_number / text serials may arrive as JSON numbers from JianDaoYun
        if ftype in ("auto_number", "text", "textarea") and isinstance(val, (int, float)) and not isinstance(val, bool):
            out[fid] = str(int(val)) if float(val).is_integer() else str(val)
            val = out[fid]
        if ftype in ("person", "user"):
            if isinstance(val, str):
                uid = await resolve_user_id(db, tenant_id, user_id=None, user_name=val, field_label=fid)
                if uid:
                    out[fid] = uid
            elif isinstance(val, dict):
                name = val.get("name") or val.get("username") or val.get("id")
                uid = await resolve_user_id(
                    db, tenant_id,
                    user_id=val.get("id") if isinstance(val.get("id"), str) else None,
                    user_name=str(name) if name else None,
                    field_label=fid,
                )
                if uid:
                    out[fid] = uid
        elif ftype in ("person_multi",):
            items = val if isinstance(val, list) else [val]
            resolved = []
            for item in items:
                if isinstance(item, str):
                    uid = await resolve_user_id(db, tenant_id, user_id=None, user_name=item, field_label=fid)
                    if uid:
                        resolved.append(uid)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("username") or item.get("id")
                    uid = await resolve_user_id(
                        db, tenant_id,
                        user_id=item.get("id") if isinstance(item.get("id"), str) else None,
                        user_name=str(name) if name else None,
                        field_label=fid,
                    )
                    if uid:
                        resolved.append(uid)
            if resolved:
                out[fid] = resolved
        elif ftype == "department":
            if isinstance(val, str):
                did = await resolve_department_id(
                    db, tenant_id, department_id=None, department_name=val,
                )
                if did:
                    out[fid] = did
            elif isinstance(val, dict):
                name = val.get("name") or val.get("id")
                did = await resolve_department_id(
                    db, tenant_id,
                    department_id=val.get("id") if isinstance(val.get("id"), str) else None,
                    department_name=str(name) if name else None,
                )
                if did:
                    out[fid] = did
        elif ftype == "department_multi":
            items = val if isinstance(val, list) else [val]
            resolved = []
            for item in items:
                if isinstance(item, str):
                    did = await resolve_department_id(
                        db, tenant_id, department_id=None, department_name=item,
                    )
                    if did:
                        resolved.append(did)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("id")
                    did = await resolve_department_id(
                        db, tenant_id,
                        department_id=item.get("id") if isinstance(item.get("id"), str) else None,
                        department_name=str(name) if name else None,
                    )
                    if did:
                        resolved.append(did)
            if resolved:
                out[fid] = resolved
        elif ftype == "detail_table" and isinstance(val, list):
            cols = {c.get("id"): c for c in (fd.get("detail_table_columns") or []) if isinstance(c, dict) and c.get("id")}
            if not cols:
                continue
            remapped = []
            for row in val:
                if not isinstance(row, dict):
                    continue
                nr = dict(row)
                for cid, cfd in cols.items():
                    if cid not in nr:
                        continue
                    ctype = cfd.get("type") or ""
                    cv = nr[cid]
                    if ctype == "person" and isinstance(cv, str):
                        uid = await resolve_user_id(db, tenant_id, user_id=None, user_name=cv, field_label=cid)
                        if uid:
                            nr[cid] = uid
                    elif ctype == "person" and isinstance(cv, dict):
                        name = cv.get("name") or cv.get("username")
                        uid = await resolve_user_id(
                            db, tenant_id, user_id=cv.get("id"), user_name=str(name) if name else None, field_label=cid,
                        )
                        if uid:
                            nr[cid] = uid
                remapped.append(nr)
            out[fid] = remapped
    return out


async def _find_form_instance_by_external_key(
    db: AsyncSession, tenant_id: str, template_id: str, external_key: str,
):
    from app.domains.lowcode.models import FormInstance
    return (await db.execute(
        select(FormInstance).where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.template_id == template_id,
            FormInstance.is_deleted == False,  # noqa: E712
            FormInstance.form_data["_external_key"].as_string() == external_key,
        ).limit(1)
    )).scalar_one_or_none()


def _form_instance_to_openapi_dto(inst) -> dict:
    return {
        "id": inst.id,
        "template_id": inst.template_id,
        "title": inst.title,
        "status": inst.status,
        "business_no": inst.business_no,
        "external_key": (inst.form_data or {}).get("_external_key"),
        "created_at": inst.created_at.isoformat() if getattr(inst, "created_at", None) else None,
        "updated_at": inst.updated_at.isoformat() if getattr(inst, "updated_at", None) else None,
    }


async def create_form_instance_from_openapi(db: AsyncSession, ctx, data) -> dict:
    """Create or update a low-code form instance pushed by middleware."""
    from app.domains.lowcode import service as lc_service
    from app.domains.lowcode import schemas as lc_schemas
    from app.domains.lowcode.field_permission import SYSTEM_ROLE
    from app.domains.openapi.errors import OpenApiException, CRM_VALIDATION_ERROR

    code = (data.template_code or "").strip()
    if code not in _OPENAPI_FORM_CODES:
        raise OpenApiException(
            CRM_VALIDATION_ERROR,
            f"unsupported template_code: {code}",
            http_status=422,
            details={"allowed": sorted(_OPENAPI_FORM_CODES)},
        )
    external_key = (data.external_key or "").strip()
    if not external_key:
        raise OpenApiException(CRM_VALIDATION_ERROR, "external_key is required", http_status=422)

    tpl = await lc_service.get_template_by_code(db, ctx.tenant_id, code)
    if not tpl:
        # Try ensure builtin once
        try:
            await lc_service.ensure_builtin_form(db, ctx.tenant_id, code, {
                "sub": ctx.app_id, "username": "openapi", "real_name": "开放平台",
            })
        except Exception:
            pass
        tpl = await lc_service.get_template_by_code(db, ctx.tenant_id, code)
    if not tpl:
        raise OpenApiException(
            CRM_VALIDATION_ERROR,
            f"form template {code} not found; ensure builtin templates on CRM first",
            http_status=422,
        )

    published = await lc_service._get_published_version(db, ctx.tenant_id, tpl.id)
    field_defs = (published.field_definitions if published else []) or []

    form_data = dict(data.form_data or {})
    form_data["_external_key"] = external_key
    form_data["_external_source"] = "jdy"
    form_data = await _normalize_openapi_form_data(db, ctx.tenant_id, field_defs, form_data)

    user = {
        "sub": ctx.app_id,
        "username": f"openapi:{ctx.app_key}",
        "real_name": "开放平台",
        "roles": [SYSTEM_ROLE],
        "dept_id": None,
    }

    existing = await _find_form_instance_by_external_key(db, ctx.tenant_id, tpl.id, external_key)
    if existing:
        upd = lc_schemas.FormInstanceUpdate(
            title=data.title,
            remark=data.remark,
            form_data=form_data,
        )
        inst = await lc_service.update_instance(db, ctx.tenant_id, existing.id, upd, user)
        return {**_form_instance_to_openapi_dto(inst), "upsert": "updated"}

    create = lc_schemas.FormInstanceCreate(
        template_id=tpl.id,
        title=data.title,
        remark=data.remark,
        form_data=form_data,
        as_draft=bool(data.as_draft),
    )
    # Prefer applicant as initiator when resolved
    applicant = form_data.get("applicant")
    if isinstance(applicant, str) and applicant:
        user["sub"] = applicant
    inst = await lc_service.create_instance(db, ctx.tenant_id, create, user)
    return {**_form_instance_to_openapi_dto(inst), "upsert": "created"}


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
