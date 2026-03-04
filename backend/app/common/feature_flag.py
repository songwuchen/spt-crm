"""Feature flag enforcement utility.

Reads from the `tenant_feature_toggles` table to check whether a feature
is enabled for a given tenant.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import TenantFeatureToggle


async def is_feature_enabled(db: AsyncSession, tenant_id: str, feature_code: str) -> bool:
    """Check if a feature is enabled for the given tenant.

    Returns True if:
    - The toggle row exists and enabled=True, OR
    - The toggle row does not exist (features are on by default).
    """
    ft = (await db.execute(
        select(TenantFeatureToggle).where(
            TenantFeatureToggle.tenant_id == tenant_id,
            TenantFeatureToggle.feature_code == feature_code,
        )
    )).scalar_one_or_none()
    if ft is None:
        return True  # Default: enabled
    return ft.enabled


async def get_feature_config(db: AsyncSession, tenant_id: str, feature_code: str) -> dict | None:
    """Get the config_json for a feature toggle, or None if not found."""
    ft = (await db.execute(
        select(TenantFeatureToggle).where(
            TenantFeatureToggle.tenant_id == tenant_id,
            TenantFeatureToggle.feature_code == feature_code,
        )
    )).scalar_one_or_none()
    if ft is None:
        return None
    return ft.config_json
