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


def verify_password(plain: str, hashed: str | None) -> bool:
    """校验密码，存储的 hash 非法时返回 False 而不是抛异常。

    ``bcrypt.checkpw`` 对空串/非 bcrypt 值会抛 ValueError（``invalid salt``），对 None
    则是 AttributeError。这两种脏数据都可能出现（历史数据、测试夹具直接写
    ``password_hash="x"``），而登录是在候选用户列表上逐个校验的——一个坏账号
    足以让同名/同手机号的其他租户用户一并登录失败并返回 500。
    """
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


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
        tenant_id = await _resolve_tenant_id_by_code(db, tenant_code.strip())
        if not tenant_id:
            raise BusinessException(code=UNAUTHORIZED, message="用户名或密码错误")
        query = query.where(User.tenant_id == tenant_id)

    candidates = (await db.execute(query)).scalars().all()
    matched = [u for u in candidates if verify_password(password, u.password_hash)]
    if not matched:
        raise BusinessException(code=UNAUTHORIZED, message="用户名或密码错误")
    if len(matched) > 1:
        tenants = await _tenant_options_for_users(db, matched)
        raise BusinessException(
            code=UNAUTHORIZED,
            message="该账号存在于多个租户，请选择租户后重新登录",
            detail={"need_tenant": True, "tenants": tenants},
        )
    return matched[0]


# 本地/演示主租户：历史数据常有用户，却未写入 platform_tenants，导致无法用 tenant_code 消歧
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_TENANT_CODE = "default"


async def _resolve_tenant_id_by_code(db: AsyncSession, tenant_code: str) -> str | None:
    from app.domains.tenant.models import PlatformTenant

    if tenant_code == DEFAULT_TENANT_CODE:
        return DEFAULT_TENANT_ID
    tenant = (await db.execute(
        select(PlatformTenant).where(PlatformTenant.code == tenant_code)
    )).scalar_one_or_none()
    return tenant.id if tenant else None


async def _tenant_options_for_users(db: AsyncSession, users: list[User]) -> list[dict]:
    """为多租户登录冲突构造前端可选列表。"""
    from app.domains.tenant.models import PlatformTenant

    tenant_ids = list(dict.fromkeys(u.tenant_id for u in users))
    rows = (await db.execute(
        select(PlatformTenant).where(PlatformTenant.id.in_(tenant_ids))
    )).scalars().all()
    by_id = {t.id: t for t in rows}
    out: list[dict] = []
    # 主租户优先，登录页默认选中更符合本地常用场景
    ordered = sorted(
        tenant_ids,
        key=lambda tid: (0 if tid == DEFAULT_TENANT_ID else 1, tid),
    )
    for tid in ordered:
        t = by_id.get(tid)
        if t:
            out.append({"code": t.code, "name": t.name, "id": t.id})
        elif tid == DEFAULT_TENANT_ID:
            out.append({"code": DEFAULT_TENANT_CODE, "name": "默认租户", "id": tid})
        else:
            out.append({"code": tid[:8], "name": f"租户({tid[:8]})", "id": tid})
    return out


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
    # 迁移/脏数据可能导致 permission_id 悬空，relationship 为 None；跳过避免登录 500
    perms = list({rp.permission.code for rp in role_perms if rp.permission is not None})
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
