import bcrypt
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import UNAUTHORIZED
from app.domains.auth.models import User, UserRole, RolePermission

# Login lockout: max 5 failures within 15 minutes
MAX_LOGIN_FAILURES = 5
LOCKOUT_WINDOW_MINUTES = 15


async def _check_lockout(db: AsyncSession, username: str) -> None:
    """Check if account is locked due to too many failed login attempts."""
    try:
        from app.domains.audit.models import AuditLog
        since = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
        count = (await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "login_failed",
                AuditLog.summary.ilike(f"%{username}%"),
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


async def authenticate(db: AsyncSession, username: str, password: str, tenant_code: str | None = None) -> User:
    await _check_lockout(db, username)
    query = select(User).where(User.username == username, User.is_active == True)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise BusinessException(code=UNAUTHORIZED, message="用户名或密码错误")
    return user


async def get_user_permissions(db: AsyncSession, user_id: str, tenant_id: str) -> list[str]:
    """Collect all permission codes for a user via their roles."""
    query = (
        select(RolePermission)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    )
    result = await db.execute(query)
    role_perms = result.scalars().all()
    return list({rp.permission.code for rp in role_perms})


async def get_user_roles(db: AsyncSession, user_id: str, tenant_id: str) -> list[str]:
    query = select(UserRole).where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
    result = await db.execute(query)
    user_roles = result.scalars().all()
    return [ur.role.code for ur in user_roles]
