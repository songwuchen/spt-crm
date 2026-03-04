"""
Field-level masking decorator for API responses.
Masks sensitive fields (cost, margin, discount, etc.) based on user permissions.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# Default masking rules (used if no DB policy configured)
DEFAULT_MASK_POLICIES = [
    {"resource": "quote_version", "field": "margin_rate", "required_permission": "quote:view_cost", "mask_type": "hidden"},
    {"resource": "quote_line", "field": "cost_est", "required_permission": "quote:view_cost", "mask_type": "hidden"},
    {"resource": "cost_snapshot", "field": "cost_total", "required_permission": "quote:view_cost", "mask_type": "hidden"},
    {"resource": "cost_snapshot", "field": "breakdown_json", "required_permission": "quote:view_cost", "mask_type": "hidden"},
    {"resource": "quote_version", "field": "discount_total", "required_permission": "quote:view_discount", "mask_type": "hidden"},
    {"resource": "contract", "field": "amount_total", "required_permission": "contract:view_amount", "mask_type": "hidden"},
]

MASK_VALUE = "***"


async def load_mask_policies(db: AsyncSession, tenant_id: str) -> list[dict]:
    """Load field mask policies from DB, fall back to defaults."""
    try:
        from app.domains.admin.models import TenantFeatureToggle
        toggle = (await db.execute(
            select(TenantFeatureToggle).where(
                TenantFeatureToggle.tenant_id == tenant_id,
                TenantFeatureToggle.feature_code == "field_masking",
            )
        )).scalar_one_or_none()
        if toggle and not toggle.enabled:
            return []  # Feature disabled
        if toggle and toggle.config_json and isinstance(toggle.config_json, list):
            return toggle.config_json
    except Exception:
        pass
    return DEFAULT_MASK_POLICIES


def apply_field_mask(data: dict | list, resource: str, user_permissions: list[str], policies: list[dict]) -> Any:
    """Apply field masking to response data based on policies and user permissions."""
    if not policies:
        return data

    # Find relevant policies for this resource
    relevant = [p for p in policies if p.get("resource") == resource]
    if not relevant:
        return data

    if isinstance(data, list):
        return [_mask_dict(item, relevant, user_permissions) for item in data]
    elif isinstance(data, dict):
        return _mask_dict(data, relevant, user_permissions)
    return data


def _mask_dict(d: dict, policies: list[dict], user_permissions: list[str]) -> dict:
    if not isinstance(d, dict):
        return d
    result = dict(d)
    for policy in policies:
        field = policy.get("field", "")
        required_perm = policy.get("required_permission", "")
        if field in result and required_perm and required_perm not in user_permissions:
            mask_type = policy.get("mask_type", "hidden")
            if mask_type == "hidden":
                result[field] = MASK_VALUE
            elif mask_type == "null":
                result[field] = None
            elif mask_type == "zero":
                result[field] = 0
    return result
