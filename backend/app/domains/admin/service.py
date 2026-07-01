from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.admin.models import (
    TenantPlan, TenantUsageMeter, TenantProfile, TenantFeatureToggle,
    StageDefinition, MarginPolicy, TenantAiPolicy, TenantAiBudget,
    IntegrationEndpoint, WebhookSubscription, ApprovalPolicy,
    TenantStorageConfig,
)
from app.domains.tenant.models import PlatformTenant
from app.domains.audit.service import log_action


# ==================== Platform: Tenant Plans ====================

async def list_plans(db: AsyncSession):
    result = await db.execute(select(TenantPlan).order_by(TenantPlan.created_at.desc()))
    return result.scalars().all()


async def create_plan(db: AsyncSession, data: dict) -> TenantPlan:
    plan = TenantPlan(id=generate_uuid(), **data)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_plan(db: AsyncSession, plan_id: str, data: dict) -> TenantPlan:
    plan = (await db.execute(select(TenantPlan).where(TenantPlan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise BusinessException(code=NOT_FOUND, message="套餐不存在")
    for k, v in data.items():
        setattr(plan, k, v)
    await db.commit()
    await db.refresh(plan)
    return plan


# ==================== Platform: Tenant Management ====================

async def list_tenants(db: AsyncSession):
    result = await db.execute(select(PlatformTenant).order_by(PlatformTenant.created_at.desc()))
    return result.scalars().all()


async def update_tenant(db: AsyncSession, tenant_id: str, data: dict) -> PlatformTenant:
    t = (await db.execute(select(PlatformTenant).where(PlatformTenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise BusinessException(code=NOT_FOUND, message="租户不存在")
    for k, v in data.items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return t


# ==================== Tenant: Profile ====================

async def get_profile(db: AsyncSession, tenant_id: str) -> TenantProfile | None:
    return (await db.execute(
        select(TenantProfile).where(TenantProfile.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def upsert_profile(db: AsyncSession, tenant_id: str, data: dict) -> TenantProfile:
    profile = await get_profile(db, tenant_id)
    if profile:
        for k, v in data.items():
            setattr(profile, k, v)
    else:
        profile = TenantProfile(id=generate_uuid(), tenant_id=tenant_id, **data)
        db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


# ==================== Tenant: UI Settings (界面设置) ====================

async def get_ui_settings(db: AsyncSession, tenant_id: str) -> dict:
    """界面个性化设置。未配置时返回空别名/空隐藏/空系统名（前端回退默认）。"""
    p = await get_profile(db, tenant_id)
    return {
        "system_name": p.system_name if p else None,
        "menu_aliases": (p.menu_aliases_json if p and p.menu_aliases_json else {}),
        "hidden_menus": (p.hidden_menus_json if p and p.hidden_menus_json else []),
    }


async def update_ui_settings(db: AsyncSession, tenant_id: str, data: dict) -> dict:
    """整体覆盖保存界面设置（复用 TenantProfile 行）。"""
    await upsert_profile(db, tenant_id, {
        "system_name": data.get("system_name"),
        "menu_aliases_json": data.get("menu_aliases") or {},
        "hidden_menus_json": data.get("hidden_menus") or [],
    })
    return await get_ui_settings(db, tenant_id)


# ==================== Tenant: Feature Toggles ====================

async def list_features(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(TenantFeatureToggle).where(TenantFeatureToggle.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def upsert_feature(db: AsyncSession, tenant_id: str, feature_code: str, data: dict) -> TenantFeatureToggle:
    ft = (await db.execute(
        select(TenantFeatureToggle).where(
            TenantFeatureToggle.tenant_id == tenant_id,
            TenantFeatureToggle.feature_code == feature_code,
        )
    )).scalar_one_or_none()
    if ft:
        for k, v in data.items():
            setattr(ft, k, v)
    else:
        ft = TenantFeatureToggle(id=generate_uuid(), tenant_id=tenant_id, feature_code=feature_code, **data)
        db.add(ft)
    await db.commit()
    await db.refresh(ft)
    return ft


# ==================== Tenant: Stage Definitions ====================

async def list_stages(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(StageDefinition).where(StageDefinition.tenant_id == tenant_id).order_by(StageDefinition.sort_order)
    )
    return result.scalars().all()


async def upsert_stage(db: AsyncSession, tenant_id: str, stage_code: str, data: dict) -> StageDefinition:
    sd = (await db.execute(
        select(StageDefinition).where(
            StageDefinition.tenant_id == tenant_id,
            StageDefinition.stage_code == stage_code,
        )
    )).scalar_one_or_none()
    if sd:
        for k, v in data.items():
            setattr(sd, k, v)
    else:
        sd = StageDefinition(id=generate_uuid(), tenant_id=tenant_id, stage_code=stage_code, **data)
        db.add(sd)
    await db.commit()
    await db.refresh(sd)
    return sd


# ==================== Tenant: Margin Policies ====================

async def list_margin_policies(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(MarginPolicy).where(MarginPolicy.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def create_margin_policy(db: AsyncSession, tenant_id: str, data: dict) -> MarginPolicy:
    mp = MarginPolicy(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(mp)
    await db.commit()
    await db.refresh(mp)
    return mp


async def update_margin_policy(db: AsyncSession, tenant_id: str, policy_id: str, data: dict) -> MarginPolicy:
    mp = (await db.execute(
        select(MarginPolicy).where(MarginPolicy.id == policy_id, MarginPolicy.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not mp:
        raise BusinessException(code=NOT_FOUND, message="策略不存在")
    for k, v in data.items():
        setattr(mp, k, v)
    await db.commit()
    await db.refresh(mp)
    return mp


# ==================== Tenant: AI Policy ====================

async def list_ai_policies(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(TenantAiPolicy).where(TenantAiPolicy.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def upsert_ai_policy(db: AsyncSession, tenant_id: str, task_type: str, data: dict) -> TenantAiPolicy:
    ap = (await db.execute(
        select(TenantAiPolicy).where(
            TenantAiPolicy.tenant_id == tenant_id,
            TenantAiPolicy.task_type == task_type,
        )
    )).scalar_one_or_none()
    if ap:
        for k, v in data.items():
            setattr(ap, k, v)
    else:
        ap = TenantAiPolicy(id=generate_uuid(), tenant_id=tenant_id, task_type=task_type, **data)
        db.add(ap)
    await db.commit()
    await db.refresh(ap)
    return ap


# ==================== Tenant: AI Budget ====================

async def get_ai_budget(db: AsyncSession, tenant_id: str, period: str) -> TenantAiBudget | None:
    return (await db.execute(
        select(TenantAiBudget).where(
            TenantAiBudget.tenant_id == tenant_id,
            TenantAiBudget.period == period,
        )
    )).scalar_one_or_none()


async def upsert_ai_budget(db: AsyncSession, tenant_id: str, data: dict) -> TenantAiBudget:
    period = data.pop("period")
    budget = await get_ai_budget(db, tenant_id, period)
    if budget:
        for k, v in data.items():
            setattr(budget, k, v)
    else:
        budget = TenantAiBudget(id=generate_uuid(), tenant_id=tenant_id, period=period, **data)
        db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


# ==================== Tenant: Approval Policies ====================

async def list_approval_policies(db: AsyncSession, tenant_id: str, biz_type: str | None = None):
    q = select(ApprovalPolicy).where(ApprovalPolicy.tenant_id == tenant_id)
    if biz_type:
        q = q.where(ApprovalPolicy.biz_type == biz_type)
    result = await db.execute(q.order_by(ApprovalPolicy.priority.desc()))
    return result.scalars().all()


async def create_approval_policy(db: AsyncSession, tenant_id: str, data: dict) -> ApprovalPolicy:
    ap = ApprovalPolicy(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(ap)
    await db.commit()
    await db.refresh(ap)
    return ap


async def update_approval_policy(db: AsyncSession, tenant_id: str, policy_id: str, data: dict) -> ApprovalPolicy:
    ap = (await db.execute(
        select(ApprovalPolicy).where(ApprovalPolicy.id == policy_id, ApprovalPolicy.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not ap:
        raise BusinessException(code=NOT_FOUND, message="审批策略不存在")
    for k, v in data.items():
        setattr(ap, k, v)
    await db.commit()
    await db.refresh(ap)
    return ap


async def delete_approval_policy(db: AsyncSession, tenant_id: str, policy_id: str):
    ap = (await db.execute(
        select(ApprovalPolicy).where(ApprovalPolicy.id == policy_id, ApprovalPolicy.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if ap:
        await db.delete(ap)
        await db.commit()


async def match_approval_policy(db: AsyncSession, tenant_id: str, biz_type: str, context: dict) -> ApprovalPolicy | None:
    """Find the first matching approval policy based on biz_type and conditions."""
    policies = await list_approval_policies(db, tenant_id, biz_type)
    for policy in policies:
        if not policy.enabled:
            continue
        if _match_conditions(policy.condition_json, context):
            return policy
    return None


_NUMERIC_OPS = ("gte", "lte", "gt", "lt")


def _match_conditions(condition_json: dict | None, context: dict) -> bool:
    """Check if context matches the policy conditions (AND across all keys).

    Keys are `<field>_<op>` where op is one of gt/gte/lt/lte/eq/ne.
    Numeric ops (gt/gte/lt/lte) require the field to be present and numeric.
    eq/ne compare as strings, so they work for enum/text fields.
    A bare `<field>` key (no op suffix) is treated as loose exact match for
    backward compatibility. Referencing a field the context can't supply
    (numeric ops or eq) fails to match, so a policy never triggers on data it
    can't evaluate.
    """
    if not condition_json or not isinstance(condition_json, dict):
        return True  # No conditions = always match
    for key, value in condition_json.items():
        op = None
        field = key
        for suffix in ("gte", "lte", "gt", "lt", "eq", "ne"):
            if key.endswith("_" + suffix):
                op = suffix
                field = key[: -(len(suffix) + 1)]
                break

        actual = context.get(field)

        if op in _NUMERIC_OPS:
            if actual is None:
                return False
            try:
                a, b = float(actual), float(value)
            except (TypeError, ValueError):
                return False
            if op == "gt" and not (a > b):
                return False
            if op == "gte" and not (a >= b):
                return False
            if op == "lt" and not (a < b):
                return False
            if op == "lte" and not (a <= b):
                return False
        elif op == "eq":
            if actual is None or str(actual) != str(value):
                return False
        elif op == "ne":
            if actual is not None and str(actual) == str(value):
                return False
        else:
            # Bare key: loose exact match (absent field passes)
            if actual is not None and str(actual) != str(value):
                return False
    return True


# ==================== Tenant: Integrations ====================

async def list_integrations(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(IntegrationEndpoint).where(IntegrationEndpoint.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def create_integration(db: AsyncSession, tenant_id: str, data: dict) -> IntegrationEndpoint:
    from app.common.crypto import encrypt_config_json
    if "auth_config_json" in data:
        data["auth_config_json"] = encrypt_config_json(data["auth_config_json"])
    ep = IntegrationEndpoint(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return ep


async def update_integration(db: AsyncSession, tenant_id: str, ep_id: str, data: dict) -> IntegrationEndpoint:
    from app.common.crypto import encrypt_config_json
    ep = (await db.execute(
        select(IntegrationEndpoint).where(IntegrationEndpoint.id == ep_id, IntegrationEndpoint.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not ep:
        raise BusinessException(code=NOT_FOUND, message="集成端点不存在")
    if "auth_config_json" in data:
        data["auth_config_json"] = encrypt_config_json(data["auth_config_json"])
    for k, v in data.items():
        setattr(ep, k, v)
    await db.commit()
    await db.refresh(ep)
    return ep


async def get_integration(db: AsyncSession, tenant_id: str, ep_id: str) -> IntegrationEndpoint | None:
    return (await db.execute(
        select(IntegrationEndpoint).where(IntegrationEndpoint.id == ep_id, IntegrationEndpoint.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def delete_integration(db: AsyncSession, tenant_id: str, ep_id: str):
    ep = (await db.execute(
        select(IntegrationEndpoint).where(IntegrationEndpoint.id == ep_id, IntegrationEndpoint.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if ep:
        await db.delete(ep)
        await db.commit()


# ==================== Tenant: File Storage ====================

_STORAGE_PROVIDERS = ("minio", "oss")


async def _get_storage_row(db: AsyncSession, tenant_id: str) -> TenantStorageConfig | None:
    return (await db.execute(
        select(TenantStorageConfig).where(TenantStorageConfig.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def get_storage_config_masked(db: AsyncSession, tenant_id: str) -> dict:
    """Config for the settings UI — secret values masked, never returned in clear."""
    from app.common.crypto import mask_config_json
    row = await _get_storage_row(db, tenant_id)
    cfg = (row.config_json if row else None) or {}
    return {
        "storage_type": row.storage_type if row else "local",
        "minio": mask_config_json(cfg.get("minio")) or {},
        "oss": mask_config_json(cfg.get("oss")) or {},
    }


def _merge_provider(existing: dict | None, incoming: dict | None) -> dict | None:
    """Merge an incoming provider config over the stored one, keeping existing
    encrypted secrets when the UI sends back a masked/empty secret_key."""
    from app.common.crypto import encrypt_config_json
    if incoming is None:
        return existing
    merged = dict(existing or {})
    for k, v in incoming.items():
        if v is None:
            continue
        # Preserve the stored secret when the client echoes the masked placeholder.
        if k == "secret_key" and v in ("", "***"):
            continue
        merged[k] = v
    return encrypt_config_json(merged)


async def upsert_storage_config(db: AsyncSession, tenant_id: str, data: dict) -> TenantStorageConfig:
    row = await _get_storage_row(db, tenant_id)
    current = (row.config_json if row else None) or {}
    new_config = dict(current)
    for provider in _STORAGE_PROVIDERS:
        if provider in data and data[provider] is not None:
            new_config[provider] = _merge_provider(current.get(provider), data[provider])

    storage_type = data.get("storage_type") or (row.storage_type if row else "local")
    if row:
        row.storage_type = storage_type
        row.config_json = new_config
    else:
        row = TenantStorageConfig(
            id=generate_uuid(), tenant_id=tenant_id,
            storage_type=storage_type, config_json=new_config,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def resolve_storage_backend(db: AsyncSession, tenant_id: str, storage_type: str | None = None):
    """Return a ready-to-use StorageBackend.

    ``storage_type`` overrides the active backend — used by the download/delete
    paths to reach a file on the backend it was actually stored on.
    """
    from app.common.crypto import decrypt_config_json
    from app.domains.attachment.storage import get_backend
    row = await _get_storage_row(db, tenant_id)
    active_type = storage_type or (row.storage_type if row else "local")
    cfg = (row.config_json if row else None) or {}
    provider_cfg = decrypt_config_json(cfg.get(active_type)) if active_type in _STORAGE_PROVIDERS else None
    return get_backend(active_type, provider_cfg), active_type


async def test_storage_connection(db: AsyncSession, tenant_id: str, storage_type: str) -> tuple[bool, str | None]:
    import asyncio
    from app.domains.attachment.storage import StorageError
    try:
        backend, _ = await resolve_storage_backend(db, tenant_id, storage_type)
    except StorageError as e:
        return False, str(e)
    return await asyncio.to_thread(backend.test_connection)


# ==================== Tenant: Webhooks ====================

async def list_webhooks(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.tenant_id == tenant_id)
    )
    return result.scalars().all()


async def create_webhook(db: AsyncSession, tenant_id: str, data: dict) -> WebhookSubscription:
    ws = WebhookSubscription(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return ws


async def delete_webhook(db: AsyncSession, tenant_id: str, ws_id: str):
    ws = (await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == ws_id, WebhookSubscription.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if ws:
        await db.delete(ws)
        await db.commit()
