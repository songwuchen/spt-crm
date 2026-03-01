"""
Data visibility scope filter.
Restricts list queries based on owner, department chain, and ACL shares.
Non-admin users only see records they own or that are shared with them.
"""
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select


async def apply_data_scope(
    query: Select,
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    model,
    biz_type: str,
) -> Select:
    """Apply data scope filtering to a SQLAlchemy select query.

    Admin users (with '*' permission or 'admin:all') bypass scoping.
    Other users see records where:
    - owner_id == current user
    - OR record is shared via acl_shares to this user
    - OR record is shared to user's department
    """
    user_perms = user.get("permissions", [])
    user_roles = user.get("roles", [])

    # Admin bypass
    if "*" in user_perms or "admin" in user_roles or "super_admin" in user_roles:
        return query

    user_id = user.get("sub", "")
    if not user_id:
        return query

    # Build OR conditions
    conditions = []

    # 1. Owned by current user
    if hasattr(model, "owner_id"):
        conditions.append(model.owner_id == user_id)

    # 2. Created by current user
    if hasattr(model, "created_by_id"):
        conditions.append(model.created_by_id == user_id)

    # 3. Shared via ACL
    try:
        from app.domains.outbox.models import AclShare
        shared_biz_ids_q = select(AclShare.biz_id).where(
            AclShare.tenant_id == tenant_id,
            AclShare.biz_type == biz_type,
            or_(
                AclShare.shared_to_id == user_id,
                AclShare.shared_to_type == "all",
            ),
        )
        conditions.append(model.id.in_(shared_biz_ids_q))
    except (ImportError, Exception):
        pass

    # 4. Department-based visibility: user's department members' records
    try:
        dept_id = user.get("dept_id")
        if dept_id and hasattr(model, "owner_id"):
            from app.domains.organization.models import DepartmentMember
            dept_user_ids_q = select(DepartmentMember.user_id).where(
                DepartmentMember.tenant_id == tenant_id,
                DepartmentMember.department_id == dept_id,
            )
            conditions.append(model.owner_id.in_(dept_user_ids_q))
    except (ImportError, Exception):
        pass

    if conditions:
        query = query.where(or_(*conditions))

    return query
