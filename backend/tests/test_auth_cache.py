"""Unit tests for auth permission/role cache invalidation (issue #49).

These do not need a database — they exercise the cache layer directly to ensure
the invalidation helpers delete exactly the keys that ``get_user_permissions`` /
``get_user_roles`` write. If the key format ever drifts apart, role changes would
silently keep serving stale permissions to re-logging-in users again.
"""

from app.common.cache import cache_set, cache_get
from app.domains.auth.service import (
    invalidate_user_auth_cache,
    invalidate_tenant_auth_cache,
)

TENANT = "tenant-x"


async def test_invalidate_user_auth_cache_clears_perms_and_roles():
    user = "user-1"
    await cache_set(f"user_perms:{TENANT}:{user}", ["customer:view"])
    await cache_set(f"user_roles:{TENANT}:{user}", ["sales"])

    await invalidate_user_auth_cache(user, TENANT)

    assert await cache_get(f"user_perms:{TENANT}:{user}") is None
    assert await cache_get(f"user_roles:{TENANT}:{user}") is None


async def test_invalidate_user_auth_cache_scoped_to_user():
    await cache_set(f"user_perms:{TENANT}:keep", ["x"])
    await cache_set(f"user_perms:{TENANT}:drop", ["y"])

    await invalidate_user_auth_cache("drop", TENANT)

    assert await cache_get(f"user_perms:{TENANT}:drop") is None
    assert await cache_get(f"user_perms:{TENANT}:keep") == ["x"]


async def test_invalidate_tenant_auth_cache_clears_all_users():
    await cache_set(f"user_perms:{TENANT}:a", ["1"])
    await cache_set(f"user_perms:{TENANT}:b", ["2"])
    await cache_set(f"user_roles:{TENANT}:a", ["r"])

    await invalidate_tenant_auth_cache(TENANT)

    assert await cache_get(f"user_perms:{TENANT}:a") is None
    assert await cache_get(f"user_perms:{TENANT}:b") is None
    assert await cache_get(f"user_roles:{TENANT}:a") is None
