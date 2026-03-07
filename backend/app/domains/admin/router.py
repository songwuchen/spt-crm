from typing import Optional, Union
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.database import gen_id
from app.domains.admin import service
from app.domains.admin.models import DocTemplate, EmailTemplate, CustomFieldDef
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
