from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.admin import service
from app.domains.admin.schemas import (
    TenantPlanCreate, TenantPlanUpdate, PlatformTenantUpdate,
    TenantProfileUpdate, FeatureToggleUpdate, StageDefinitionUpdate,
    MarginPolicyCreate, MarginPolicyUpdate, AiPolicyUpdate, AiBudgetUpdate,
    IntegrationCreate, IntegrationUpdate, WebhookCreate,
    ApprovalPolicyCreate, ApprovalPolicyUpdate,
)

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
