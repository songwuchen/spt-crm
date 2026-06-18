import bcrypt
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import UNAUTHORIZED
from app.domains.auth.models import User, UserRole, RolePermission

# Login lockout: max 5 failures within 15 minutes
MAX_LOGIN_FAILURES = 5
LOCKOUT_WINDOW_MINUTES = 15


async def _check_lockout(db: AsyncSession, username: str, client_ip: str = "") -> None:
    """Check if too many failed login attempts happened recently.

    Scoped by client IP (the failed-login audit row records ``... from <ip>``) so that
    failures originating from one source cannot lock out a user signing in from elsewhere.
    This matters because usernames are NOT globally unique across tenants — without IP
    scoping an attacker could lock out a same-named user in another tenant.
    """
    try:
        from app.domains.audit.models import AuditLog
        since = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
        # The failed-login summary is "登录失败: <username> from <ip>".
        if client_ip:
            summary_match = AuditLog.summary.ilike(f"%: {username} from {client_ip}%")
        else:
            summary_match = AuditLog.summary.ilike(f"%: {username} from %")
        count = (await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "login_failed",
                summary_match,
                AuditLog.created_at >= since,
            )
        )).scalar() or 0
        if count >= MAX_LOGIN_FAILURES:
            raise BusinessException(
                code=UNAUTHORIZED,
                message=f"账户已锁定，请{LOCKOUT_WINDOW_MINUTES}分钟后再试"
            )
    except BusinessException:
        raise
    except Exception:
        pass  # If audit table unavailable, skip lockout check


async def authenticate(
    db: AsyncSession,
    username: str,
    password: str,
    tenant_code: str | None = None,
    client_ip: str = "",
) -> User:
    """Authenticate a user by username/password.

    登录标识（``username`` 参数）既可以是用户名，也可以是手机号（issue #48）。

    Usernames are unique only within a tenant, not globally. When a ``tenant_code`` is
    supplied the lookup is scoped to that tenant. Otherwise we verify the password against
    every active user holding that identifier and require an unambiguous single match — this
    prevents silently logging into the wrong tenant (and avoids a raw MultipleResultsFound
    crash) when two tenants happen to share a username/phone.
    """
    await _check_lockout(db, username, client_ip)
    # 允许用用户名或手机号登录
    query = select(User).where(
        or_(User.username == username, User.phone == username),
        User.is_active == True,
    )
    if tenant_code:
        from app.domains.tenant.models import PlatformTenant
        tenant = (await db.execute(
            select(PlatformTenant).where(PlatformTenant.code == tenant_code)
        )).scalar_one_or_none()
        if not tenant:
            raise BusinessException(code=UNAUTHORIZED, message="用户名或密码错误")
        query = query.where(User.tenant_id == tenant.id)

    candidates = (await db.execute(query)).scalars().all()
    matched = [u for u in candidates if bcrypt.checkpw(password.encode(), u.password_hash.encode())]
    if not matched:
        raise BusinessException(code=UNAUTHORIZED, message="用户名或密码错误")
    if len(matched) > 1:
        raise BusinessException(code=UNAUTHORIZED, message="该账号存在于多个租户，请提供租户标识后重新登录")
    return matched[0]


async def invalidate_user_auth_cache(user_id: str, tenant_id: str) -> None:
    """清除某个用户的权限/角色缓存。

    角色变更后必须调用，否则用户重新登录（含钉钉登录）在缓存 TTL（5 分钟）内
    仍会拿到旧角色/旧权限。见 issue #49。
    """
    from app.common.cache import cache_delete
    await cache_delete(f"user_perms:{tenant_id}:{user_id}")
    await cache_delete(f"user_roles:{tenant_id}:{user_id}")


async def invalidate_tenant_auth_cache(tenant_id: str) -> None:
    """清除整个租户下所有用户的权限/角色缓存。

    用于角色本身的权限被修改的场景（一个角色可能被很多用户持有，
    无法只失效单个用户）。
    """
    from app.common.cache import cache_delete_pattern
    await cache_delete_pattern(f"user_perms:{tenant_id}:*")
    await cache_delete_pattern(f"user_roles:{tenant_id}:*")


async def get_user_permissions(db: AsyncSession, user_id: str, tenant_id: str) -> list[str]:
    """Collect all permission codes for a user via their roles. Cached for 5 min."""
    from app.common.cache import cache_get, cache_set
    cache_key = f"user_perms:{tenant_id}:{user_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    query = (
        select(RolePermission)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    )
    result = await db.execute(query)
    role_perms = result.scalars().all()
    perms = list({rp.permission.code for rp in role_perms})
    await cache_set(cache_key, perms, ttl=300)
    return perms


async def get_user_roles(db: AsyncSession, user_id: str, tenant_id: str) -> list[str]:
    from app.common.cache import cache_get, cache_set
    cache_key = f"user_roles:{tenant_id}:{user_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    query = select(UserRole).where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    result = await db.execute(query)
    user_roles = result.scalars().all()
    roles = [ur.role.code for ur in user_roles]
    await cache_set(cache_key, roles, ttl=300)
    return roles
