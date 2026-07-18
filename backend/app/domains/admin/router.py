import asyncio
import io
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional, Union
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete as sa_delete, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.database import generate_uuid as gen_id, async_session_factory
from app.domains.admin import service
from app.domains.admin.models import DocTemplate, EmailTemplate
from app.common.exceptions import BusinessException
from app.domains.admin.schemas import (
    TenantPlanCreate, TenantPlanUpdate, PlatformTenantUpdate,
    TenantProfileUpdate, FeatureToggleUpdate, StageDefinitionUpdate,
    MarginPolicyCreate, MarginPolicyUpdate, AiPolicyUpdate, AiBudgetUpdate,
    IntegrationCreate, IntegrationUpdate, WebhookCreate,
    ApprovalPolicyCreate, ApprovalPolicyUpdate, StorageConfigUpdate,
    UiSettingsUpdate, AiSettingUpdate,
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


# ==================== Tenant: UI Settings (界面设置) ====================

@router.get("/api/admin/v1/tenant/ui-settings")
async def get_ui_settings(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db)):
    """界面个性化设置 — 任意登录用户可读（前端用于渲染菜单别名/隐藏与品牌名）。"""
    return ok(await service.get_ui_settings(db, tenant_id))


@router.put("/api/admin/v1/tenant/ui-settings")
async def update_ui_settings(body: UiSettingsUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    """整体覆盖保存界面设置（仅 role:manage）。"""
    return ok(await service.update_ui_settings(db, tenant_id, body.model_dump()))


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

    # Cache backend (redis vs in-memory) — 用于验证线上 Redis 是否真正启用
    try:
        from app.common.cache import cache_backend
        cache_status = cache_backend()
    except Exception:
        cache_status = {"backend": "unknown", "configured": False, "connected": False}

    return ok({
        "db": {"ok": db_ok, "latency_ms": db_latency_ms, "pool": pool_stats},
        "cache": cache_status,
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


# ==================== Tenant: File Storage ====================

@router.get("/api/admin/v1/tenant/file-storage")
async def get_file_storage(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    return ok(await service.get_storage_config_masked(db, tenant_id))


@router.put("/api/admin/v1/tenant/file-storage")
async def update_file_storage(body: StorageConfigUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    data = body.model_dump(exclude_unset=True)
    # Normalise the provider sub-objects to plain dicts
    for provider in ("minio", "oss"):
        if data.get(provider) is not None and not isinstance(data[provider], dict):
            data[provider] = data[provider].model_dump(exclude_unset=True)
    await service.upsert_storage_config(db, tenant_id, data)
    return ok(await service.get_storage_config_masked(db, tenant_id))


@router.post("/api/admin/v1/tenant/file-storage/test")
async def test_file_storage(storage_type: str = Query(...), tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    if storage_type not in ("local", "minio", "oss"):
        raise BusinessException(message="不支持的存储类型")
    connected, err = await service.test_storage_connection(db, tenant_id, storage_type)
    return ok({"connected": connected, "error": err})


# ==================== Tenant: AI 模型接入 ====================

@router.get("/api/admin/v1/tenant/ai-settings")
async def get_ai_settings(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    return ok(await service.get_ai_setting_masked(db, tenant_id))


@router.put("/api/admin/v1/tenant/ai-settings")
async def update_ai_settings(body: AiSettingUpdate, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    data = body.model_dump(exclude_unset=True)
    for key in ("chat", "embedding"):
        if data.get(key) is not None and not isinstance(data[key], dict):
            data[key] = data[key].model_dump(exclude_unset=True)
    await service.upsert_ai_setting(db, tenant_id, data)
    return ok(await service.get_ai_setting_masked(db, tenant_id))


@router.post("/api/admin/v1/tenant/ai-settings/test-chat")
async def test_ai_chat_conn(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    connected, err = await service.test_ai_chat(db, tenant_id)
    return ok({"connected": connected, "error": err})


@router.post("/api/admin/v1/tenant/ai-settings/test-embedding")
async def test_ai_embedding_conn(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("role:manage"))):
    connected, err = await service.test_ai_embedding(db, tenant_id)
    return ok({"connected": connected, "error": err})


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
    t = (await db.execute(
        select(DocTemplate).where(DocTemplate.id == template_id, DocTemplate.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not t:
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
                    created_by_id=current_user["sub"],
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
    t = (await db.execute(
        select(DocTemplate).where(DocTemplate.id == template_id, DocTemplate.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not t:
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
    t = (await db.execute(
        select(DocTemplate).where(DocTemplate.id == template_id, DocTemplate.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if t:
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


# ==================== Custom Field Definitions（已下线） ====================
# 旧自定义字段引擎已被 lowcode 表单引擎取代（统一到表单引擎）。
# /api/v1/custom-fields 接口已移除；CustomFieldDef 模型与 custom_field_defs 表
# 暂保留（不做破坏性迁移），历史定义数据仍在库中，如需可离线导出。


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
                select(model_cls).where(model_cls.id == record["id"], model_cls.tenant_id == tenant_id)
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
    dict_type: str = Field(..., min_length=1, max_length=64)
    # A non-empty, unique code per type is required: an empty/duplicated code makes
    # the frontend <Select> unable to tell options apart, so every selection renders
    # the last-added label (issue #96).
    dict_code: str = Field(..., min_length=1, max_length=64)
    dict_label: str = Field(..., min_length=1, max_length=200)
    sort_order: int = 0
    color: Optional[str] = None
    extra_json: Optional[dict] = None
    enabled: bool = True


async def _ensure_dict_code_unique(db, tenant_id: str, dict_type: str, dict_code: str, exclude_id: Optional[str] = None):
    q = select(DataDictionary).where(
        DataDictionary.tenant_id == tenant_id,
        DataDictionary.dict_type == dict_type,
        DataDictionary.dict_code == dict_code,
        DataDictionary.is_deleted == False,
    )
    if exclude_id:
        q = q.where(DataDictionary.id != exclude_id)
    if (await db.execute(q)).scalar_one_or_none():
        raise BusinessException(code=400, message=f"编码「{dict_code}」在该字典类型下已存在")


@router.post("/api/v1/data-dict")
async def create_data_dict(
    body: DataDictBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    code = body.dict_code.strip()
    await _ensure_dict_code_unique(db, tenant_id, body.dict_type, code)
    item = DataDictionary(
        id=gen_id(), tenant_id=tenant_id,
        dict_type=body.dict_type, dict_code=code,
        dict_label=body.dict_label.strip(), sort_order=body.sort_order,
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
    code = body.dict_code.strip()
    await _ensure_dict_code_unique(db, tenant_id, body.dict_type, code, exclude_id=item_id)
    item.dict_type = body.dict_type
    item.dict_code = code
    item.dict_label = body.dict_label.strip()
    for k in ("sort_order", "color", "extra_json", "enabled"):
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


# ==================== Customer Data Purge ====================

_purge_logger = logging.getLogger("purge")

# In-memory task tracking: tenant_id -> task info dict
_purge_tasks: dict[str, dict] = {}


class PurgeScheduleBody(BaseModel):
    delay_seconds: int = Field(default=300, ge=60, le=3600)


async def _execute_purge(tenant_id: str, task_id: str, user_id: str, user_name: str | None):
    """Background coroutine: run the actual purge after the asyncio.sleep completes."""
    task_info = _purge_tasks.get(tenant_id)
    if not task_info or task_info["task_id"] != task_id:
        return  # was cancelled or replaced

    task_info["status"] = "executing"

    try:
        async with async_session_factory() as db:
            # Import all related models
            from app.domains.customer.models import Customer, Contact, CustomerRelation, AclShare
            from app.domains.project.models import OpportunityProject
            from app.domains.quote.models import Quote, QuoteVersion, QuoteLine, CostSnapshot, QuoteSendLog
            from app.domains.contract.models import Contract
            from app.domains.solution.models import Solution
            from app.domains.delivery.models import DeliveryMilestone
            from app.domains.payment.models import PaymentPlan, Invoice, PaymentRecord
            from app.domains.change.models import ChangeRequest
            from app.domains.service_ticket.models import ServiceTicket, RenewalOpportunity
            from app.domains.activity.models import Activity

            # Collect customer IDs first
            cust_ids_result = await db.execute(
                select(Customer.id).where(Customer.tenant_id == tenant_id)
            )
            customer_ids = [row[0] for row in cust_ids_result.all()]

            deleted_counts: dict[str, int] = {}

            if customer_ids:
                # Delete related records that reference customer_id
                for label, model, fk_col in [
                    ("contacts", Contact, Contact.customer_id),
                    ("customer_relations_from", CustomerRelation, CustomerRelation.from_customer_id),
                    ("customer_relations_to", CustomerRelation, CustomerRelation.to_customer_id),
                    ("service_tickets", ServiceTicket, ServiceTicket.customer_id),
                    ("renewal_opportunities", RenewalOpportunity, RenewalOpportunity.customer_id),
                ]:
                    result = await db.execute(
                        sa_delete(model).where(
                            model.tenant_id == tenant_id,
                            fk_col.in_(customer_ids),
                        )
                    )
                    deleted_counts[label] = deleted_counts.get(label, 0) + result.rowcount

                # Projects linked to customers
                proj_ids_result = await db.execute(
                    select(OpportunityProject.id).where(
                        OpportunityProject.tenant_id == tenant_id,
                        OpportunityProject.customer_id.in_(customer_ids),
                    )
                )
                project_ids = [row[0] for row in proj_ids_result.all()]

                if project_ids:
                    # Collect quote IDs for sub-table deletion
                    quote_ids_result = await db.execute(
                        select(Quote.id).where(
                            Quote.tenant_id == tenant_id,
                            Quote.project_id.in_(project_ids),
                        )
                    )
                    quote_ids = [row[0] for row in quote_ids_result.all()]

                    if quote_ids:
                        # Collect quote version IDs
                        qv_ids_result = await db.execute(
                            select(QuoteVersion.id).where(
                                QuoteVersion.tenant_id == tenant_id,
                                QuoteVersion.quote_id.in_(quote_ids),
                            )
                        )
                        qv_ids = [row[0] for row in qv_ids_result.all()]

                        if qv_ids:
                            # Delete quote lines and cost snapshots (ref quote_version_id)
                            for label, model in [
                                ("quote_lines", QuoteLine),
                                ("cost_snapshots", CostSnapshot),
                            ]:
                                result = await db.execute(
                                    sa_delete(model).where(
                                        model.tenant_id == tenant_id,
                                        model.quote_version_id.in_(qv_ids),
                                    )
                                )
                                deleted_counts[label] = result.rowcount

                        # Delete quote versions and send logs (ref quote_id)
                        for label, model, fk in [
                            ("quote_versions", QuoteVersion, QuoteVersion.quote_id),
                            ("quote_send_logs", QuoteSendLog, QuoteSendLog.quote_id),
                        ]:
                            result = await db.execute(
                                sa_delete(model).where(
                                    model.tenant_id == tenant_id,
                                    fk.in_(quote_ids),
                                )
                            )
                            deleted_counts[label] = result.rowcount

                    # Delete project-related records that have project_id
                    for label, model in [
                        ("quotes", Quote),
                        ("contracts", Contract),
                        ("solutions", Solution),
                        ("delivery_milestones", DeliveryMilestone),
                        ("payment_plans", PaymentPlan),
                        ("invoices", Invoice),
                        ("payment_records", PaymentRecord),
                        ("change_requests", ChangeRequest),
                    ]:
                        result = await db.execute(
                            sa_delete(model).where(
                                model.tenant_id == tenant_id,
                                model.project_id.in_(project_ids),
                            )
                        )
                        deleted_counts[label] = result.rowcount

                    # Delete projects themselves
                    result = await db.execute(
                        sa_delete(OpportunityProject).where(
                            OpportunityProject.tenant_id == tenant_id,
                            OpportunityProject.customer_id.in_(customer_ids),
                        )
                    )
                    deleted_counts["projects"] = result.rowcount

                # Delete ACL shares for customers
                result = await db.execute(
                    sa_delete(AclShare).where(
                        AclShare.tenant_id == tenant_id,
                        AclShare.biz_type == "customer",
                        AclShare.biz_id.in_(customer_ids),
                    )
                )
                deleted_counts["acl_shares"] = result.rowcount

                # Delete activities linked to customers
                result = await db.execute(
                    sa_delete(Activity).where(
                        Activity.tenant_id == tenant_id,
                        Activity.biz_type == "customer",
                        Activity.biz_id.in_(customer_ids),
                    )
                )
                deleted_counts["activities"] = result.rowcount

                # Finally delete all customers
                result = await db.execute(
                    sa_delete(Customer).where(Customer.tenant_id == tenant_id)
                )
                deleted_counts["customers"] = result.rowcount

            await db.commit()

            # Write audit log for completion
            from app.domains.audit.service import log_action
            async with async_session_factory() as audit_db:
                await log_action(
                    audit_db, tenant_id=tenant_id,
                    user_id=user_id, user_name=user_name,
                    action="purge_completed", resource_type="customer",
                    summary=f"客户数据清空完成，共删除 {deleted_counts.get('customers', 0)} 个客户及相关数据",
                    detail={"deleted_counts": deleted_counts},
                )

        task_info["status"] = "completed"
        task_info["completed_at"] = datetime.now(timezone.utc).isoformat()
        task_info["deleted_counts"] = deleted_counts
        _purge_logger.info("Purge completed for tenant %s: %s", tenant_id, deleted_counts)

    except asyncio.CancelledError:
        task_info["status"] = "cancelled"
        _purge_logger.info("Purge cancelled for tenant %s", tenant_id)
    except Exception as exc:
        task_info["status"] = "failed"
        task_info["error"] = str(exc)
        _purge_logger.exception("Purge failed for tenant %s", tenant_id)


async def _purge_delay_then_execute(
    tenant_id: str, task_id: str, delay_seconds: int,
    user_id: str, user_name: str | None,
):
    """Sleep for delay, then run the purge."""
    try:
        await asyncio.sleep(delay_seconds)
        await _execute_purge(tenant_id, task_id, user_id, user_name)
    except asyncio.CancelledError:
        task_info = _purge_tasks.get(tenant_id)
        if task_info and task_info["task_id"] == task_id:
            task_info["status"] = "cancelled"


@router.post("/api/admin/v1/tenant/customers/purge")
async def schedule_purge(
    body: PurgeScheduleBody = PurgeScheduleBody(),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("role:manage")),
):
    """Schedule a delayed purge of all customer data for this tenant."""
    existing = _purge_tasks.get(tenant_id)
    if existing and existing["status"] in ("scheduled", "executing"):
        raise BusinessException(code=400, message="已有清空任务正在进行中，请先取消或等待完成")

    task_id = gen_id()
    now = datetime.now(timezone.utc)
    execute_at = datetime.fromtimestamp(now.timestamp() + body.delay_seconds, tz=timezone.utc)

    user_id = current_user["sub"]
    user_name = current_user.get("real_name")

    # Create the background asyncio task
    loop_task = asyncio.create_task(
        _purge_delay_then_execute(tenant_id, task_id, body.delay_seconds, user_id, user_name)
    )

    _purge_tasks[tenant_id] = {
        "task_id": task_id,
        "status": "scheduled",
        "asyncio_task": loop_task,
        "scheduled_at": now.isoformat(),
        "execute_at": execute_at.isoformat(),
        "delay_seconds": body.delay_seconds,
        "user_id": user_id,
        "user_name": user_name,
    }

    # Audit log for scheduling
    from app.domains.audit.service import log_action
    await log_action(
        db, tenant_id=tenant_id,
        user_id=user_id, user_name=user_name,
        action="purge_scheduled", resource_type="customer",
        summary=f"计划清空全部客户数据，延迟 {body.delay_seconds} 秒后执行",
        detail={"task_id": task_id, "delay_seconds": body.delay_seconds,
                "execute_at": execute_at.isoformat()},
    )

    return ok({
        "task_id": task_id,
        "status": "scheduled",
        "scheduled_at": now.isoformat(),
        "execute_at": execute_at.isoformat(),
        "delay_seconds": body.delay_seconds,
    })


@router.get("/api/admin/v1/tenant/customers/purge/status")
async def purge_status(
    tenant_id: str = Depends(get_tenant_id),
    _user=Depends(require_permissions("role:manage")),
):
    """Get the current purge task status for this tenant."""
    task_info = _purge_tasks.get(tenant_id)
    if not task_info:
        return ok({"status": "idle"})

    result = {
        "task_id": task_info["task_id"],
        "status": task_info["status"],
        "scheduled_at": task_info.get("scheduled_at"),
        "execute_at": task_info.get("execute_at"),
        "delay_seconds": task_info.get("delay_seconds"),
        "completed_at": task_info.get("completed_at"),
        "deleted_counts": task_info.get("deleted_counts"),
        "error": task_info.get("error"),
    }
    return ok(result)


@router.post("/api/admin/v1/tenant/customers/purge/cancel")
async def cancel_purge(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("role:manage")),
):
    """Cancel a scheduled purge before it executes."""
    task_info = _purge_tasks.get(tenant_id)
    if not task_info or task_info["status"] != "scheduled":
        raise BusinessException(code=400, message="没有可取消的清空任务")

    # Cancel the asyncio task
    asyncio_task = task_info.get("asyncio_task")
    if asyncio_task and not asyncio_task.done():
        asyncio_task.cancel()

    task_info["status"] = "cancelled"

    # Audit log
    from app.domains.audit.service import log_action
    user_id = current_user["sub"]
    user_name = current_user.get("real_name")
    await log_action(
        db, tenant_id=tenant_id,
        user_id=user_id, user_name=user_name,
        action="purge_cancelled", resource_type="customer",
        summary="取消了客户数据清空任务",
        detail={"task_id": task_info["task_id"]},
    )

    return ok({"status": "cancelled", "task_id": task_info["task_id"]})


# ==================== 同步标准角色与权限 (Standard RBAC sync) ====================

class RbacSyncApply(BaseModel):
    # additive: 只增不删(默认,安全); reset: 额外移除标准角色上的非标准授权
    mode: str = Field("additive", pattern=r"^(additive|reset)$")
    create_missing_roles: bool = True


@router.get("/api/admin/v1/rbac/standard-sync/preview")
async def rbac_standard_sync_preview(
    mode: str = Query("additive", pattern=r"^(additive|reset)$"),
    create_missing_roles: bool = Query(True),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """预览:把本租户的标准角色对齐到系统标准目录会发生哪些变化(只读)。"""
    from app.common import rbac_sync
    plan = await rbac_sync.preview(db, tenant_id, mode=mode, create_missing_roles=create_missing_roles)
    return ok(plan)


@router.post("/api/admin/v1/rbac/standard-sync/apply")
async def rbac_standard_sync_apply(
    body: RbacSyncApply,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions("role:manage")),
):
    """应用标准角色与权限同步(仅本租户);写审计并刷新本租户权限缓存。
    只动标准角色,不触碰自定义/人名角色。"""
    from app.common import rbac_sync
    report = await rbac_sync.apply(
        db, tenant_id, mode=body.mode, create_missing_roles=body.create_missing_roles)
    await db.commit()

    # Audit first (own session, non-fatal) so it always records the committed change.
    from app.domains.audit.service import log_action
    await log_action(
        db, tenant_id=tenant_id,
        user_id=current_user["sub"], user_name=current_user.get("real_name"),
        action="rbac_standard_sync", resource_type="role",
        summary=(f"同步标准角色与权限(mode={report['mode']}):新建 "
                 f"{len(report['created_roles'])} 个角色、新增 {report['perms_added']} 项授权、"
                 f"移除 {report['perms_removed']} 项"),
        detail=report,
    )

    # 角色权限变更后失效本租户缓存,否则最长 5 分钟才生效(issue #49)。缓存后端
    # (Redis)短暂不可用不应让一次已提交成功的同步返回 500 —— 兜底吞掉并记日志。
    try:
        from app.domains.auth.service import invalidate_tenant_auth_cache
        await invalidate_tenant_auth_cache(tenant_id)
    except Exception:
        logging.getLogger(__name__).warning(
            "rbac_standard_sync: tenant auth cache invalidation failed (non-fatal); "
            "perms take effect within the cache TTL", exc_info=True)
    return ok(report)
