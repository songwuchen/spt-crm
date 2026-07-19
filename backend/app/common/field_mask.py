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
    # 合同金额是 CRM 核心数据，凡能查看合同者即可见，不再默认脱敏（成本/毛利/折扣仍脱敏）。
    # 如某租户确需脱敏合同金额：
    #   · 按角色 → 扩展平台 → 自定义字段 → 合同 → 字段权限 → 可见明文角色（推荐，配置即生效）
    #   · 按权限 → 系统配置 → 字段脱敏(按权限)，新增 contract / amount_total 规则
]

MASK_VALUE = "***"


async def load_mask_policies(db: AsyncSession, tenant_id: str) -> list[dict]:
    """Load field mask policies from DB, fall back to defaults.

    config_json 接受两种形状：
    - {"policies": [...]}  —— 现行格式，配置 API(FeatureToggleUpdate.config_json) 是 dict；
    - [...]                —— 早期直接存数组的遗留数据，继续兼容读取。
    """
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
        cfg = toggle.config_json if toggle else None
        if isinstance(cfg, dict) and isinstance(cfg.get("policies"), list):
            return cfg["policies"]
        if isinstance(cfg, list) and cfg:
            return cfg
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


def masked_number(value: Any, default: float | None = None) -> float | None:
    """把一个「可能已脱敏」的值转成可安全用于数值渲染(PDF/Excel)的结果。

    三种 mask_type 都要照顾到，只认 "***" 是不够的：
    - hidden → 值是 "***"，无法转数字 → 返回 default；
    - null   → 值是 None                → 返回 default；
    - zero   → 值是 0，这正是该策略要展示的内容 → 原样返回 0。

    调用方必须传入**已经过 apply_field_mask 的 dict 里的值**，而不是回头去读未脱敏的
    模型属性 —— 后者会让脱敏在导出路径上完全失效。
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
