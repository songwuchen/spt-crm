import io
import json
from datetime import date, datetime
from typing import Optional, Union
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.database import generate_uuid as gen_id
from app.domains.admin import service
from app.domains.admin.models import DocTemplate, EmailTemplate, CustomFieldDef
from app.common.exceptions import BusinessException
from app.domains.admin.schemas import (
    TenantPlanCreate, TenantPlanUpdate, PlatformTenantUpdate,
    TenantProfileUpdate, FeatureToggleUpdate, StageDefinitionUpdate,
    MarginPolicyCreate, MarginPolicyUpdate, AiPolicyUpdate, AiBudgetUpdate,
    IntegrationCreate, IntegrationUpdate, WebhookCreate,
    ApprovalPolicyCreate, ApprovalPolicyUpdate,
)


class DocTemplateBody(BaseModel):
    doc_type: str = Field(..., pattern=r"^(quote|contract)$")
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    content_json: Optional[dict] = None
    is_default: bool = False


class EmailTemplateBody(BaseModel):
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=200)
    subject: Optional[str] = None
    body_html: Optional[str] = None
    variables_json: Optional[Union[dict, list]] = None
    enabled: bool = True


class CustomFieldDefBody(BaseModel):
    entity_type: str = Field(..., pattern=r"^(customer|project|lead|contact|service_ticket)$")
    field_key: str = Field(..., max_length=64)
    field_label: str = Field(..., max_length=100)
    field_type: str = Field(..., pattern=r"^(text|number|date|select|multiselect|boolean)$")
    options_json: Optional[list] = None
    required: bool = False
    sort_order: int = 0
    enabled: bool = True

router = APIRouter(tags=["管理端"])


# ==================== Platform: Plans ====================

@router.get("/api/admin/v1/platform/plans")
async def list_plans(db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_plans(db)
    return ok([_plan_dict(p) for p in items])


@router.post("/api/admin/v1/platform/plans")
async def create_plan(body: TenantPlanCreate, db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.create_plan(db, body.model_dump(exclude_unset=True))
    return ok(_plan_dict(p))


@router.put("/api/admin/v1/platform/plans/{plan_id}")
async def update_plan(plan_id: str, body: TenantPlanUpdate, db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.update_plan(db, plan_id, body.model_dump(exclude_unset=True))
    return ok(_plan_dict(p))


def _plan_dict(p) -> dict:
    return {"id": p.id, "name": p.name, "pricing_json": p.pricing_json, "limits_json": p.limits_json,
            "features_json": p.features_json, "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else ""}


# ==================== Platform: Tenants ====================

@router.get("/api/admin/v1/platform/tenants")
async def list_tenants(db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_tenants(db)
    return ok([{"id": t.id, "code": t.code, "name": t.name,
                "is_active": t.is_active, "plan": t.plan,
                "contact_name": t.contact_name, "contact_email": t.contact_email,
                "created_at": t.created_at.isoformat() if t.created_at else ""} for t in items])


@router.put("/api/admin/v1/platform/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, body: PlatformTenantUpdate, db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    t = await service.update_tenant(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": t.id, "name": t.name, "status": t.status})


# ==================== Platform: Overview & Usage ====================

@router.get("/api/admin/v1/platform/overview")
async def platform_overview(db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    """Platform-level overview: tenant counts, user counts, usage summaries."""
    from app.domains.auth.models import User
    from app.domains.tenant.models import PlatformTenant
    from app.domains.admin.models import TenantUsageMeter
    from datetime import datetime, timezone

    current_period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Tenant stats
    total_tenants = (await db.execute(select(func.count(PlatformTenant.id)))).scalar() or 0
    active_tenants = (await db.execute(
        select(func.count(PlatformTenant.id)).where(PlatformTenant.is_active == True)
    )).scalar() or 0

    # User stats (across all tenants)
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    # Usage meters for current period (aggregated across tenants)
    usage_rows = (await db.execute(
        select(
            TenantUsageMeter.metric_code,
            func.sum(TenantUsageMeter.value).label("total")
        ).where(TenantUsageMeter.period == current_period)
        .group_by(TenantUsageMeter.metric_code)
    )).all()
    usage_summary = {row.metric_code: float(row.total) for row in usage_rows}

    # Per-tenant usage for current period
    tenant_usage_rows = (await db.execute(
        select(
            TenantUsageMeter.tenant_id,
            TenantUsageMeter.metric_code,
            TenantUsageMeter.value
        ).where(TenantUsageMeter.period == current_period)
    )).all()
    tenant_usage: dict = {}
    for row in tenant_usage_rows:
        if row.tenant_id not in tenant_usage:
            tenant_usage[row.tenant_id] = {}
        tenant_usage[row.tenant_id][row.metric_code] = float(row.value)

    return ok({
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_users": total_users,
        "current_period": current_period,
        "usage_summary": usage_summary,
        "tenant_usage": tenant_usage,
    })


@router.get("/api/admin/v1/platform/usage")
async def list_usage(
    tenant_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """List usage meter records, optionally filtered by tenant/period."""
    from app.domains.admin.models import TenantUsageMeter

    q = select(TenantUsageMeter).order_by(TenantUsageMeter.period.desc())
    if tenant_id:
        q = q.where(TenantUsageMeter.tenant_id == tenant_id)
    if period:
        q = q.where(TenantUsageMeter.period == period)
    rows = (await db.execute(q.limit(500))).scalars().all()
    return ok([{
        "id": r.id, "tenant_id": r.tenant_id, "metric_code": r.metric_code,
        "period": r.period, "value": float(r.value),
    } for r in rows])


# ==================== Tenant: Profile ====================

@router.get("/api/admin/v1/tenant/profile")
async def get_profile(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.get_profile(db, tenant_id)
    if not p:
        return ok(None)
    return ok({"id": p.id, "timezone": p.timezone, "locale": p.locale,
               "logo_attachment_id": p.logo_attachment_id, "security_policy_json": p.security_policy_json,
               "data_retention_days": p.data_retention_days})


@router.put("/api/admin/v1/tenant/profile")
async def update_profile(body: TenantProfileUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.upsert_profile(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": p.id, "timezone": p.timezone, "locale": p.locale})


# ==================== Tenant: Pool Rules ====================

@router.get("/api/admin/v1/tenant/pool_rules")
async def get_pool_rules(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.get_profile(db, tenant_id)
    rules = (p.security_policy_json or {}).get("pool_rules", {}) if p else {}
    return ok(rules)


@router.put("/api/admin/v1/tenant/pool_rules")
async def update_pool_rules(body: dict, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.get_profile(db, tenant_id)
    if not p:
        p = await service.upsert_profile(db, tenant_id, {})
    policy = p.security_policy_json or {}
    policy["pool_rules"] = body
    p.security_policy_json = policy
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(p, "security_policy_json")
    await db.commit()
    return ok(body)


# ==================== System Health ====================

@router.get("/api/admin/v1/system/health")
async def system_health(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """System health dashboard: DB pool, API stats, worker heartbeat."""
    import time
    from app.database import engine

    # DB pool stats
    pool = engine.pool
    pool_stats = {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
    }

    # DB connectivity check
    db_ok = True
    db_latency_ms = 0
    try:
        t0 = time.monotonic()
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.monotonic() - t0) * 1000, 1)
    except Exception:
        db_ok = False

    # Table row counts (approximate)
    from app.domains.customer.models import Customer
    from app.domains.lead.models import Lead
    from app.domains.project.models import OpportunityProject
    from app.domains.notification.models import Notification

    counts = {}
    for name, model in [("customers", Customer), ("leads", Lead), ("projects", OpportunityProject), ("notifications", Notification)]:
        try:
            c = (await db.execute(select(func.count(model.id)).where(model.tenant_id == tenant_id))).scalar() or 0
            counts[name] = c
        except Exception:
            counts[name] = -1

    # Recent error rate (from audit logs, last 24h)
    from app.domains.audit.models import AuditLog
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    total_ops = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= day_ago,
        )
    )).scalar() or 0

    return ok({
        "db": {"ok": db_ok, "latency_ms": db_latency_ms, "pool": pool_stats},
        "table_counts": counts,
        "api": {"total_ops_24h": total_ops},
        "timestamp": now.isoformat(),
    })


# ==================== Tenant: Report Schedules ====================

@router.get("/api/admin/v1/tenant/report_schedules")
async def get_report_schedules(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.get_profile(db, tenant_id)
    schedules = (p.security_policy_json or {}).get("report_schedules", []) if p else []
    return ok(schedules)


@router.put("/api/admin/v1/tenant/report_schedules")
async def update_report_schedules(body: list, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    p = await service.get_profile(db, tenant_id)
    if not p:
        p = await service.upsert_profile(db, tenant_id, {})
    policy = p.security_policy_json or {}
    policy["report_schedules"] = body
    p.security_policy_json = policy
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(p, "security_policy_json")
    await db.commit()
    return ok(body)


# ==================== Tenant: Field Rules ====================

@router.get("/api/admin/v1/tenant/field_rules")
async def get_field_rules(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    """Get field-level visibility/masking rules per role."""
    p = await service.get_profile(db, tenant_id)
    rules = (p.security_policy_json or {}).get("field_rules", []) if p else []
    return ok(rules)


@router.put("/api/admin/v1/tenant/field_rules")
async def update_field_rules(body: list, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    """Update field-level visibility rules. Body: list of { resource, field, roles, action }."""
    p = await service.get_profile(db, tenant_id)
    if not p:
        p = await service.upsert_profile(db, tenant_id, {})
    policy = p.security_policy_json or {}
    policy["field_rules"] = body
    p.security_policy_json = policy
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(p, "security_policy_json")
    await db.commit()
    return ok(body)


# ==================== Tenant: Feature Toggles ====================

@router.get("/api/admin/v1/tenant/features")
async def list_features(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_features(db, tenant_id)
    return ok([{"id": f.id, "feature_code": f.feature_code, "enabled": f.enabled, "config_json": f.config_json} for f in items])


@router.put("/api/admin/v1/tenant/features/{feature_code}")
async def update_feature(feature_code: str, body: FeatureToggleUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    f = await service.upsert_feature(db, tenant_id, feature_code, body.model_dump(exclude_unset=True))
    return ok({"id": f.id, "feature_code": f.feature_code, "enabled": f.enabled})


# ==================== Tenant: Stage Definitions ====================

@router.get("/api/admin/v1/tenant/policies/stages")
async def list_stages(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_stages(db, tenant_id)
    return ok([{"id": s.id, "stage_code": s.stage_code, "name": s.name,
                "allowed_transitions_json": s.allowed_transitions_json, "gate_rules_json": s.gate_rules_json,
                "sort_order": s.sort_order, "enabled": s.enabled} for s in items])


@router.put("/api/admin/v1/tenant/policies/stages/{stage_code}")
async def update_stage(stage_code: str, body: StageDefinitionUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    s = await service.upsert_stage(db, tenant_id, stage_code, body.model_dump(exclude_unset=True))
    return ok({"id": s.id, "stage_code": s.stage_code, "name": s.name})


# ==================== Tenant: Margin Policies ====================

@router.get("/api/admin/v1/tenant/policies/margin")
async def list_margin(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_margin_policies(db, tenant_id)
    return ok([{"id": m.id, "policy_code": m.policy_code, "scope_json": m.scope_json,
                "redline_rate": float(m.redline_rate), "action": m.action, "enabled": m.enabled} for m in items])


@router.post("/api/admin/v1/tenant/policies/margin")
async def create_margin(body: MarginPolicyCreate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    m = await service.create_margin_policy(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": m.id, "policy_code": m.policy_code, "redline_rate": float(m.redline_rate)})


@router.put("/api/admin/v1/tenant/policies/margin/{policy_id}")
async def update_margin(policy_id: str, body: MarginPolicyUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    m = await service.update_margin_policy(db, tenant_id, policy_id, body.model_dump(exclude_unset=True))
    return ok({"id": m.id, "redline_rate": float(m.redline_rate)})


# ==================== Tenant: AI Policy ====================

@router.get("/api/admin/v1/tenant/ai/policies")
async def list_ai_policies(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_ai_policies(db, tenant_id)
    return ok([{"id": a.id, "task_type": a.task_type, "model_route_json": a.model_route_json,
                "budget_json": a.budget_json, "trigger_json": a.trigger_json,
                "guardrails_json": a.guardrails_json, "enabled": a.enabled} for a in items])


@router.put("/api/admin/v1/tenant/ai/policies/{task_type}")
async def update_ai_policy(task_type: str, body: AiPolicyUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    a = await service.upsert_ai_policy(db, tenant_id, task_type, body.model_dump(exclude_unset=True))
    return ok({"id": a.id, "task_type": a.task_type, "enabled": a.enabled})


# ==================== Tenant: AI Budget ====================

@router.get("/api/admin/v1/tenant/ai/budget")
async def get_budget(period: str = Query(...), tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    b = await service.get_ai_budget(db, tenant_id, period)
    if not b:
        return ok(None)
    return ok({"id": b.id, "period": b.period, "budget_cost": float(b.budget_cost) if b.budget_cost else None,
               "used_cost": float(b.used_cost) if b.used_cost else 0, "budget_tokens": b.budget_tokens,
               "used_tokens": b.used_tokens, "hard_limit": b.hard_limit})


@router.put("/api/admin/v1/tenant/ai/budget")
async def update_budget(body: AiBudgetUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    b = await service.upsert_ai_budget(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": b.id, "period": b.period})


# ==================== Tenant: Approval Policies ====================

@router.get("/api/admin/v1/tenant/approval-policies")
async def list_approval_policies(
    biz_type: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    items = await service.list_approval_policies(db, tenant_id, biz_type)
    return ok([{"id": a.id, "biz_type": a.biz_type, "name": a.name,
                "condition_json": a.condition_json, "approver_rules_json": a.approver_rules_json,
                "approval_mode": a.approval_mode, "sla_hours": a.sla_hours,
                "escalation_json": a.escalation_json,
                "priority": a.priority, "enabled": a.enabled} for a in items])


@router.post("/api/admin/v1/tenant/approval-policies")
async def create_approval_policy(
    body: ApprovalPolicyCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    a = await service.create_approval_policy(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": a.id, "biz_type": a.biz_type, "name": a.name})


@router.put("/api/admin/v1/tenant/approval-policies/{policy_id}")
async def update_approval_policy(
    policy_id: str,
    body: ApprovalPolicyUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    a = await service.update_approval_policy(db, tenant_id, policy_id, body.model_dump(exclude_unset=True))
    return ok({"id": a.id, "biz_type": a.biz_type, "name": a.name})


@router.delete("/api/admin/v1/tenant/approval-policies/{policy_id}")
async def delete_approval_policy(
    policy_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    await service.delete_approval_policy(db, tenant_id, policy_id)
    return ok(None)


# ==================== Tenant: Integrations ====================

@router.get("/api/admin/v1/tenant/integrations")
async def list_integrations(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_integrations(db, tenant_id)
    return ok([{"id": e.id, "system_code": e.system_code, "name": e.name,
                "base_url": e.base_url, "auth_type": e.auth_type, "status": e.status} for e in items])


@router.post("/api/admin/v1/tenant/integrations")
async def create_integration(body: IntegrationCreate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    e = await service.create_integration(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": e.id, "system_code": e.system_code})


@router.put("/api/admin/v1/tenant/integrations/{ep_id}")
async def update_integration(ep_id: str, body: IntegrationUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    e = await service.update_integration(db, tenant_id, ep_id, body.model_dump(exclude_unset=True))
    return ok({"id": e.id, "system_code": e.system_code, "status": e.status})


@router.delete("/api/admin/v1/tenant/integrations/{ep_id}")
async def delete_integration(ep_id: str, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    await service.delete_integration(db, tenant_id, ep_id)
    return ok(None)


@router.post("/api/admin/v1/tenant/integrations/{ep_id}/test")
async def test_integration(ep_id: str, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    """Test ERP integration connectivity."""
    from app.common.erp_sync import get_erp_client
    ep = await service.get_integration(db, tenant_id, ep_id)
    if not ep:
        raise BusinessException(code=44004, message="集成端点不存在")
    from app.common.erp_sync import GenericERPClient
    client = GenericERPClient(ep)
    try:
        healthy = await client.health_check()
        return ok({"connected": healthy, "system_code": ep.system_code, "base_url": ep.base_url})
    except Exception as e:
        return ok({"connected": False, "error": str(e)})


@router.post("/api/admin/v1/tenant/integrations/{ep_id}/sync-contract")
async def sync_contract(ep_id: str, contract_id: str = Query(...), tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    """Manually trigger contract sync to ERP."""
    from app.domains.contract.models import Contract
    contract = (await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not contract:
        raise BusinessException(code=44004, message="合同不存在")

    from app.common.erp_sync import get_erp_client
    ep = await service.get_integration(db, tenant_id, ep_id)
    if not ep:
        raise BusinessException(code=44004, message="集成端点不存在")

    from app.common.erp_sync import GenericERPClient
    client = GenericERPClient(ep)
    result = await client.push_contract({
        "contract_no": contract.contract_no,
        "amount_total": float(contract.amount_total) if contract.amount_total else 0,
        "sign_date": contract.sign_date.isoformat() if contract.sign_date else "",
        "customer_id": contract.customer_id or "",
    })
    return ok({"sync_result": result})


# ==================== Tenant: Webhooks ====================

@router.get("/api/admin/v1/tenant/webhooks")
async def list_webhooks(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    items = await service.list_webhooks(db, tenant_id)
    return ok([{"id": w.id, "event_types_json": w.event_types_json, "target_url": w.target_url, "status": w.status} for w in items])


@router.post("/api/admin/v1/tenant/webhooks")
async def create_webhook(body: WebhookCreate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    w = await service.create_webhook(db, tenant_id, body.model_dump(exclude_unset=True))
    return ok({"id": w.id, "target_url": w.target_url})


@router.delete("/api/admin/v1/tenant/webhooks/{ws_id}")
async def delete_webhook(ws_id: str, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    await service.delete_webhook(db, tenant_id, ws_id)
    return ok(None)


# ==================== Tenant: Doc Templates ====================

def _doc_tpl_dict(t: DocTemplate) -> dict:
    return {"id": t.id, "doc_type": t.doc_type, "name": t.name, "description": t.description,
            "content_json": t.content_json, "is_default": t.is_default,
            "created_by_name": t.created_by_name,
            "created_at": t.created_at.isoformat() if t.created_at else ""}


@router.get("/api/v1/doc-templates")
async def list_doc_templates(
    doc_type: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    q = select(DocTemplate).where(DocTemplate.tenant_id == tenant_id)
    if doc_type:
        q = q.where(DocTemplate.doc_type == doc_type)
    q = q.order_by(DocTemplate.is_default.desc(), DocTemplate.created_at.desc())
    items = (await db.execute(q)).scalars().all()
    return ok([_doc_tpl_dict(t) for t in items])


@router.get("/api/v1/doc-templates/{template_id}")
async def get_doc_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    t = await db.get(DocTemplate, template_id)
    if not t or t.tenant_id != tenant_id:
        from app.common.schemas import fail
        return fail(40400, "模板不存在")
    return ok(_doc_tpl_dict(t))


@router.post("/api/v1/doc-templates")
async def create_doc_template(
    body: DocTemplateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("role:manage")),
):
    t = DocTemplate(id=gen_id(), tenant_id=tenant_id, doc_type=body.doc_type,
                    name=body.name, description=body.description,
                    content_json=body.content_json, is_default=body.is_default,
                    created_by_id=current_user["user_id"],
                    created_by_name=current_user.get("real_name", ""))
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return ok(_doc_tpl_dict(t))


@router.put("/api/v1/doc-templates/{template_id}")
async def update_doc_template(
    template_id: str, body: DocTemplateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    t = await db.get(DocTemplate, template_id)
    if not t or t.tenant_id != tenant_id:
        from app.common.schemas import fail
        return fail(40400, "模板不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return ok(_doc_tpl_dict(t))


@router.delete("/api/v1/doc-templates/{template_id}")
async def delete_doc_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    t = await db.get(DocTemplate, template_id)
    if t and t.tenant_id == tenant_id:
        await db.delete(t)
        await db.commit()
    return ok(None)


# ==================== Tenant: Email Templates ====================

def _email_tpl_dict(t: EmailTemplate) -> dict:
    return {"id": t.id, "code": t.code, "name": t.name, "subject": t.subject,
            "body_html": t.body_html, "variables_json": t.variables_json,
            "enabled": t.enabled,
            "created_at": t.created_at.isoformat() if t.created_at else ""}


@router.get("/api/v1/email-templates")
async def list_email_templates(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    q = select(EmailTemplate).where(EmailTemplate.tenant_id == tenant_id).order_by(EmailTemplate.code)
    items = (await db.execute(q)).scalars().all()
    return ok([_email_tpl_dict(t) for t in items])


@router.post("/api/v1/email-templates")
async def create_email_template(
    body: EmailTemplateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    t = EmailTemplate(id=gen_id(), tenant_id=tenant_id, code=body.code,
                      name=body.name, subject=body.subject,
                      body_html=body.body_html, variables_json=body.variables_json,
                      enabled=body.enabled)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return ok(_email_tpl_dict(t))


@router.put("/api/v1/email-templates/{template_id}")
async def update_email_template(
    template_id: str, body: EmailTemplateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    t = await db.get(EmailTemplate, template_id)
    if not t or t.tenant_id != tenant_id:
        from app.common.schemas import fail
        return fail(40400, "模板不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return ok(_email_tpl_dict(t))


@router.delete("/api/v1/email-templates/{template_id}")
async def delete_email_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    t = await db.get(EmailTemplate, template_id)
    if t and t.tenant_id == tenant_id:
        await db.delete(t)
        await db.commit()
    return ok(None)


# ==================== Custom Field Definitions ====================

def _cf_dict(f: CustomFieldDef) -> dict:
    return {
        "id": f.id, "entity_type": f.entity_type,
        "field_key": f.field_key, "field_label": f.field_label,
        "field_type": f.field_type, "options_json": f.options_json,
        "required": f.required, "sort_order": f.sort_order, "enabled": f.enabled,
    }


@router.get("/api/v1/custom-fields")
async def list_custom_fields(
    entity_type: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    q = select(CustomFieldDef).where(CustomFieldDef.tenant_id == tenant_id)
    if entity_type:
        q = q.where(CustomFieldDef.entity_type == entity_type)
    q = q.order_by(CustomFieldDef.entity_type, CustomFieldDef.sort_order)
    items = (await db.execute(q)).scalars().all()
    return ok([_cf_dict(f) for f in items])


@router.post("/api/v1/custom-fields")
async def create_custom_field(
    body: CustomFieldDefBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    f = CustomFieldDef(id=gen_id(), tenant_id=tenant_id, **body.model_dump())
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return ok(_cf_dict(f))


@router.put("/api/v1/custom-fields/{field_id}")
async def update_custom_field(
    field_id: str,
    body: CustomFieldDefBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    f = await db.get(CustomFieldDef, field_id)
    if not f or f.tenant_id != tenant_id:
        from app.common.exceptions import BusinessException
        raise BusinessException("字段不存在")
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    await db.commit()
    await db.refresh(f)
    return ok(_cf_dict(f))


@router.delete("/api/v1/custom-fields/{field_id}")
async def delete_custom_field(
    field_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    f = await db.get(CustomFieldDef, field_id)
    if f and f.tenant_id == tenant_id:
        await db.delete(f)
        await db.commit()
    return ok(None)


# ==================== Data Backup / Restore ====================

def _model_to_dict(obj) -> dict:
    """Convert SQLAlchemy model instance to JSON-serializable dict."""
    mapper = sa_inspect(type(obj))
    d = {}
    for col in mapper.columns:
        val = getattr(obj, col.key, None)
        if isinstance(val, (datetime,)):
            val = val.isoformat()
        elif isinstance(val, (date,)):
            val = str(val)
        elif hasattr(val, '__json__'):
            val = val.__json__()
        d[col.key] = val
    return d


_BACKUP_TABLES: list[tuple[str, type]] = []


def _init_backup_tables():
    if _BACKUP_TABLES:
        return
    from app.domains.customer.models import Customer, Contact
    from app.domains.lead.models import Lead
    from app.domains.project.models import OpportunityProject
    from app.domains.quote.models import Quote, QuoteLine
    from app.domains.contract.models import Contract
    from app.domains.solution.models import Solution
    from app.domains.delivery.models import DeliveryMilestone
    from app.domains.payment.models import PaymentPlan, Invoice, PaymentRecord
    from app.domains.change.models import ChangeRequest
    from app.domains.service_ticket.models import ServiceTicket, RenewalOpportunity
    from app.domains.activity.models import Activity
    from app.domains.product.models import Product
    from app.domains.approval.models import ApprovalFlow, ApprovalTask
    from app.domains.notification.models import Notification
    from app.domains.dashboard.models import SalesTarget
    _BACKUP_TABLES.extend([
        ("customers", Customer),
        ("contacts", Contact),
        ("leads", Lead),
        ("opportunities", OpportunityProject),
        ("quotes", Quote),
        ("quote_lines", QuoteLine),
        ("contracts", Contract),
        ("solutions", Solution),
        ("delivery_milestones", DeliveryMilestone),
        ("payment_plans", PaymentPlan),
        ("invoices", Invoice),
        ("payment_records", PaymentRecord),
        ("change_requests", ChangeRequest),
        ("service_tickets", ServiceTicket),
        ("renewal_opportunities", RenewalOpportunity),
        ("activities", Activity),
        ("products", Product),
        ("approval_flows", ApprovalFlow),
        ("approval_tasks", ApprovalTask),
        ("notifications", Notification),
        ("sales_targets", SalesTarget),
    ])


@router.get("/api/v1/admin/backup")
async def backup_data(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    _init_backup_tables()
    result: dict = {"_meta": {
        "version": "1.0",
        "tenant_id": tenant_id,
        "exported_at": datetime.utcnow().isoformat(),
    }}
    for table_name, model_cls in _BACKUP_TABLES:
        rows = (await db.execute(
            select(model_cls).where(model_cls.tenant_id == tenant_id)
        )).scalars().all()
        result[table_name] = [_model_to_dict(r) for r in rows]

    buf = io.BytesIO(json.dumps(result, ensure_ascii=False, default=str).encode("utf-8"))
    filename = f"backup_{tenant_id[:8]}_{date.today().isoformat()}.json"
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/api/v1/admin/backup/stats")
async def backup_stats(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    from sqlalchemy import func
    _init_backup_tables()
    stats = {}
    for table_name, model_cls in _BACKUP_TABLES:
        cnt = (await db.execute(
            select(func.count(model_cls.id)).where(model_cls.tenant_id == tenant_id)
        )).scalar() or 0
        stats[table_name] = cnt
    return ok(stats)


@router.post("/api/v1/admin/backup/restore")
async def restore_data(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """Restore data from a backup JSON.
    Expects the same structure as the backup export.
    Existing records with matching IDs are skipped (upsert by ID).
    """

    meta = body.get("_meta", {})
    if meta.get("tenant_id") and meta["tenant_id"] != tenant_id:
        raise BusinessException(code=400, message="备份数据的租户ID不匹配")

    _init_backup_tables()
    table_map = {name: cls for name, cls in _BACKUP_TABLES}

    restored = {}
    skipped = {}
    for table_name, records in body.items():
        if table_name.startswith("_") or not isinstance(records, list):
            continue
        model_cls = table_map.get(table_name)
        if not model_cls:
            continue

        count = 0
        skip = 0
        for record in records:
            if not isinstance(record, dict) or "id" not in record:
                continue
            # Force tenant_id to current tenant
            record["tenant_id"] = tenant_id
            # Check if record already exists
            existing = (await db.execute(
                select(model_cls).where(model_cls.id == record["id"])
            )).scalar_one_or_none()
            if existing:
                skip += 1
                continue
            try:
                obj = model_cls(**{k: v for k, v in record.items() if hasattr(model_cls, k)})
                db.add(obj)
                count += 1
            except Exception:
                skip += 1
        restored[table_name] = count
        skipped[table_name] = skip

    await db.commit()
    total_restored = sum(restored.values())
    total_skipped = sum(skipped.values())
    return ok({"restored": restored, "skipped": skipped, "total_restored": total_restored, "total_skipped": total_skipped})


# ==================== Email Templates ====================

@router.get("/api/v1/admin/email-templates")
async def list_email_templates(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    items = (await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.tenant_id == tenant_id,
        ).order_by(EmailTemplate.code)
    )).scalars().all()
    return ok([{
        "id": t.id, "code": t.code, "name": t.name, "subject": t.subject,
        "body_html": t.body_html, "variables_json": t.variables_json,
        "enabled": t.enabled,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    } for t in items])


@router.post("/api/v1/admin/email-templates")
async def create_email_template(
    body: EmailTemplateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    tmpl = EmailTemplate(
        tenant_id=tenant_id, code=body.code, name=body.name,
        subject=body.subject, body_html=body.body_html,
        variables_json=body.variables_json, enabled=body.enabled,
    )
    db.add(tmpl)
    await db.commit()
    return ok({"id": tmpl.id, "code": tmpl.code, "name": tmpl.name})


@router.put("/api/v1/admin/email-templates/{tmpl_id}")
async def update_email_template(
    tmpl_id: str,
    body: EmailTemplateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    tmpl = (await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == tmpl_id, EmailTemplate.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not tmpl:
        raise BusinessException(code=404, message="模板不存在")
    tmpl.code = body.code
    tmpl.name = body.name
    tmpl.subject = body.subject
    tmpl.body_html = body.body_html
    tmpl.variables_json = body.variables_json
    tmpl.enabled = body.enabled
    await db.commit()
    return ok(None)


@router.delete("/api/v1/admin/email-templates/{tmpl_id}")
async def delete_email_template(
    tmpl_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    tmpl = (await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == tmpl_id, EmailTemplate.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not tmpl:
        raise BusinessException(code=404, message="模板不存在")
    tmpl.is_deleted = True
    await db.commit()
    return ok(None)


# ==================== Custom Fields ====================

class CustomFieldBody(BaseModel):
    entity_type: str = Field(..., pattern=r"^(customer|project|lead|contact|service_ticket)$")
    field_key: str = Field(..., max_length=64)
    field_label: str = Field(..., max_length=100)
    field_type: str = Field(..., pattern=r"^(text|number|date|select|multiselect|boolean)$")
    options_json: Optional[Union[dict, list]] = None
    required: bool = False
    sort_order: int = 0
    enabled: bool = True


@router.get("/api/v1/custom-fields")
async def list_custom_fields(
    entity_type: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    q = select(CustomFieldDef).where(
        CustomFieldDef.tenant_id == tenant_id,
    )
    if entity_type:
        q = q.where(CustomFieldDef.entity_type == entity_type)
    items = (await db.execute(q.order_by(CustomFieldDef.entity_type, CustomFieldDef.sort_order))).scalars().all()
    return ok([{
        "id": f.id, "entity_type": f.entity_type, "field_key": f.field_key,
        "field_label": f.field_label, "field_type": f.field_type,
        "options_json": f.options_json, "required": f.required,
        "sort_order": f.sort_order, "enabled": f.enabled,
    } for f in items])


@router.post("/api/v1/custom-fields")
async def create_custom_field(
    body: CustomFieldBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    field = CustomFieldDef(
        tenant_id=tenant_id, entity_type=body.entity_type,
        field_key=body.field_key, field_label=body.field_label,
        field_type=body.field_type, options_json=body.options_json,
        required=body.required, sort_order=body.sort_order, enabled=body.enabled,
    )
    db.add(field)
    await db.commit()
    return ok({"id": field.id})


@router.put("/api/v1/custom-fields/{field_id}")
async def update_custom_field(
    field_id: str,
    body: CustomFieldBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    field = (await db.execute(
        select(CustomFieldDef).where(CustomFieldDef.id == field_id, CustomFieldDef.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not field:
        raise BusinessException(code=404, message="字段不存在")
    for attr in ("entity_type", "field_key", "field_label", "field_type", "options_json", "required", "sort_order", "enabled"):
        setattr(field, attr, getattr(body, attr))
    await db.commit()
    return ok(None)


@router.delete("/api/v1/custom-fields/{field_id}")
async def delete_custom_field(
    field_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    field = (await db.execute(
        select(CustomFieldDef).where(CustomFieldDef.id == field_id, CustomFieldDef.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not field:
        raise BusinessException(code=404, message="字段不存在")
    field.is_deleted = True
    await db.commit()
    return ok(None)


# ==================== Data Dictionary ====================
from app.domains.admin.models import DataDictionary


@router.get("/api/v1/data-dict")
async def list_data_dict(
    dict_type: Optional[str] = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    q = select(DataDictionary).where(
        DataDictionary.tenant_id == tenant_id,
        DataDictionary.is_deleted == False,
    )
    if dict_type:
        q = q.where(DataDictionary.dict_type == dict_type)
    q = q.order_by(DataDictionary.dict_type, DataDictionary.sort_order)
    items = (await db.execute(q)).scalars().all()
    return ok([{
        "id": i.id, "dict_type": i.dict_type, "dict_code": i.dict_code,
        "dict_label": i.dict_label, "sort_order": i.sort_order,
        "color": i.color, "extra_json": i.extra_json, "enabled": i.enabled,
    } for i in items])


class DataDictBody(BaseModel):
    dict_type: str = Field(..., max_length=64)
    dict_code: str = Field(..., max_length=64)
    dict_label: str = Field(..., max_length=200)
    sort_order: int = 0
    color: Optional[str] = None
    extra_json: Optional[dict] = None
    enabled: bool = True


@router.post("/api/v1/data-dict")
async def create_data_dict(
    body: DataDictBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    item = DataDictionary(
        id=gen_id(), tenant_id=tenant_id,
        dict_type=body.dict_type, dict_code=body.dict_code,
        dict_label=body.dict_label, sort_order=body.sort_order,
        color=body.color, extra_json=body.extra_json, enabled=body.enabled,
    )
    db.add(item)
    await db.commit()
    return ok({"id": item.id})


@router.put("/api/v1/data-dict/{item_id}")
async def update_data_dict(
    item_id: str,
    body: DataDictBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    item = (await db.execute(
        select(DataDictionary).where(DataDictionary.id == item_id, DataDictionary.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not item:
        raise BusinessException(code=404, message="字典项不存在")
    for k in ("dict_type", "dict_code", "dict_label", "sort_order", "color", "extra_json", "enabled"):
        setattr(item, k, getattr(body, k))
    await db.commit()
    return ok(None)


@router.delete("/api/v1/data-dict/{item_id}")
async def delete_data_dict(
    item_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    item = (await db.execute(
        select(DataDictionary).where(DataDictionary.id == item_id, DataDictionary.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not item:
        raise BusinessException(code=404, message="字典项不存在")
    item.is_deleted = True
    await db.commit()
    return ok(None)


# ==================== Recycle Bin ====================
from app.domains.customer.models import Customer
from app.domains.lead.models import Lead
from app.domains.project.models import OpportunityProject


@router.get("/api/v1/recycle-bin")
async def list_recycle_bin(
    biz_type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page_no: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    """List soft-deleted records across entity types."""
    from sqlalchemy import union_all, literal_column, String as SAString, cast

    results = []
    model_map = {
        "customer": (Customer, "name", "customer_code"),
        "lead": (Lead, "company_name", "source"),
        "project": (OpportunityProject, "name", "project_code"),
    }
    types_to_query = [biz_type] if biz_type and biz_type in model_map else list(model_map.keys())

    for t in types_to_query:
        model, name_col, code_col = model_map[t]
        q = select(
            model.id,
            getattr(model, name_col).label("name"),
            getattr(model, code_col).label("code"),
            model.updated_at,
        ).where(model.tenant_id == tenant_id, model.is_deleted == True)
        if keyword:
            q = q.where(getattr(model, name_col).ilike(f"%{keyword}%"))
        items = (await db.execute(q.order_by(model.updated_at.desc()))).all()
        for row in items:
            results.append({
                "id": row[0], "name": row[1], "code": row[2],
                "biz_type": t, "deleted_at": row[3].isoformat() if row[3] else None,
            })

    # Sort by deleted_at desc
    results.sort(key=lambda x: x["deleted_at"] or "", reverse=True)
    total = len(results)
    page_results = results[(page_no - 1) * page_size: page_no * page_size]
    return ok({"items": page_results, "total": total})


@router.post("/api/v1/recycle-bin/{biz_type}/{record_id}/restore")
async def restore_record(
    biz_type: str,
    record_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """Restore a soft-deleted record."""
    model_map = {"customer": Customer, "lead": Lead, "project": OpportunityProject}
    model = model_map.get(biz_type)
    if not model:
        raise BusinessException(code=400, message="不支持的类型")
    record = (await db.execute(
        select(model).where(model.id == record_id, model.tenant_id == tenant_id, model.is_deleted == True)
    )).scalar_one_or_none()
    if not record:
        raise BusinessException(code=404, message="记录不存在或未被删除")
    record.is_deleted = False
    await db.commit()
    return ok(None)


@router.delete("/api/v1/recycle-bin/{biz_type}/{record_id}")
async def permanently_delete_record(
    biz_type: str,
    record_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """Permanently delete a soft-deleted record."""
    model_map = {"customer": Customer, "lead": Lead, "project": OpportunityProject}
    model = model_map.get(biz_type)
    if not model:
        raise BusinessException(code=400, message="不支持的类型")
    record = (await db.execute(
        select(model).where(model.id == record_id, model.tenant_id == tenant_id, model.is_deleted == True)
    )).scalar_one_or_none()
    if not record:
        raise BusinessException(code=404, message="记录不存在或未被删除")
    await db.delete(record)
    await db.commit()
    return ok(None)
