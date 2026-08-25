from typing import List
from fastapi import Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database as database
from app.common.exceptions import BusinessException
from app.common.error_codes import UNAUTHORIZED, FORBIDDEN


async def get_db() -> AsyncSession:
    # Look up the factory via the module attribute so tests can swap
    # ``app.database.async_session_factory`` (NullPool per event loop) without
    # leaving this dependency bound to a disposed engine.
    async with database.async_session_factory() as session:
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


def require_any_permission(*perms: str):
    """Factory: user must have at least ONE of the listed permissions."""

    async def _checker(current_user: dict = Depends(get_current_user)):
        user_perms: List[str] = current_user.get("permissions", [])
        if any(p in user_perms for p in perms):
            return current_user
        raise BusinessException(
            code=FORBIDDEN,
            message=f"缺少权限: {' / '.join(perms)}",
        )

    return _checker


async def require_form_list_access(
    template_id: str = Query(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """表单列表/导出：form_data:view 或曾参与该模板下任一流程（审批人可见对应列表）。"""
    perms = current_user.get("permissions") or []
    if "form_data:view" in perms:
        return current_user
    from app.domains.lowcode import workflow_service as wsvc
    uid = current_user.get("sub")
    if uid and await wsvc.user_participates_in_form_template_workflow(
        db, tenant_id, uid, template_id,
    ):
        return current_user
    raise BusinessException(code=FORBIDDEN, message="缺少权限: form_data:view")


async def get_data_scope(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> "list[str] | None":
    """返回可见数据的 owner_id 列表，None 表示不限（按角色 data_scope: self/dept/all）。"""
    from app.common.data_scope import resolve_owner_scope
    return await resolve_owner_scope(db, current_user)
