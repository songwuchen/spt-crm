from typing import List
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.common.exceptions import BusinessException
from app.common.error_codes import UNAUTHORIZED, FORBIDDEN


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def get_current_user(request: Request) -> dict:
    """Parse JWT from Authorization header and return payload dict."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise BusinessException(code=UNAUTHORIZED, message="未认证")

    token = auth_header[7:]
    from app.domains.auth.jwt_handler import decode_token
    payload = decode_token(token, expected_type="access")

    # Also store on request.state for middleware access
    request.state.current_user = payload
    request.state.tenant_id = payload.get("tenant_id")
    return payload


async def get_tenant_id(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise BusinessException(code=UNAUTHORIZED, message="租户信息缺失")

    # Check tenant active status
    from app.domains.tenant.models import PlatformTenant
    tenant = (await db.execute(
        select(PlatformTenant).where(PlatformTenant.id == tenant_id)
    )).scalar_one_or_none()
    if tenant and not tenant.is_active:
        raise BusinessException(code=FORBIDDEN, message="租户已停用，请联系管理员")

    return tenant_id


def require_permissions(*perms: str):
    """Factory: returns a dependency that checks the user has ALL listed permissions."""

    async def _checker(current_user: dict = Depends(get_current_user)):
        user_perms: List[str] = current_user.get("permissions", [])
        for p in perms:
            if p not in user_perms:
                raise BusinessException(code=FORBIDDEN, message=f"缺少权限: {p}")
        return current_user

    return _checker


async def get_data_scope(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> "list[str] | None":
    """返回可见数据的 owner_id 列表，None 表示不限（按角色 data_scope: self/dept/all）。"""
    from app.common.data_scope import resolve_owner_scope
    return await resolve_owner_scope(db, current_user)
