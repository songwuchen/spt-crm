"""
Data visibility scope filter.

数据可见范围由「角色的 data_scope」决定（取用户多个角色中最大的一档）：
  - all  : 全部租户数据（管理员、data:view_all，或任一角色 data_scope=all）
  - dept : 本人所在部门及其所有下级部门的成员所拥有的数据
  - self : 仅本人拥有的数据（默认）

`resolve_owner_scope` 返回可见 owner_id 列表（None 表示不限）。
`apply_data_scope` 在 owner 范围之外，额外并入「创建人/共享/项目成员」等可见性（用于商机）。
"""
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select


def _is_admin(user: dict) -> bool:
    perms = user.get("permissions", [])
    roles = user.get("roles", [])
    return "*" in perms or "data:view_all" in perms or "admin" in roles or "super_admin" in roles


async def resolve_owner_scope(db: AsyncSession, user: dict, tenant_id: str | None = None) -> list[str] | None:
    """返回当前用户可见数据的 owner_id 集合；None 表示不限（可见全部）。"""
    if _is_admin(user):
        return None
    uid = user.get("sub")
    tid = tenant_id or user.get("tenant_id")
    if not uid:
        return None

    from app.domains.auth.models import Role, UserRole
    from app.domains.organization.models import Department, UserDepartment

    scopes = set((await db.execute(
        select(Role.data_scope)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == uid, UserRole.tenant_id == tid)
    )).scalars().all())

    if "all" in scopes:
        return None
    if "dept" in scopes:
        my_dept_ids = (await db.execute(
            select(UserDepartment.department_id).where(
                UserDepartment.user_id == uid, UserDepartment.tenant_id == tid)
        )).scalars().all()
        if my_dept_ids:
            my_paths = (await db.execute(
                select(Department.path).where(
                    Department.id.in_(my_dept_ids), Department.tenant_id == tid)
            )).scalars().all()
            # 子树（含本部门）：path 以本部门 path 为前缀的所有部门
            conds = [Department.path.like(p + "%") for p in my_paths if p]
            subtree_ids = set(my_dept_ids)
            if conds:
                subtree_ids |= set((await db.execute(
                    select(Department.id).where(Department.tenant_id == tid, or_(*conds))
                )).scalars().all())
            members = (await db.execute(
                select(UserDepartment.user_id).where(
                    UserDepartment.department_id.in_(subtree_ids), UserDepartment.tenant_id == tid)
            )).scalars().all()
            ids = {m for m in members if m}
            ids.add(uid)
            return list(ids)
    return [uid]


def scoped_owners(owner_id: str | None, scope: list[str] | None) -> list[str] | None:
    """把「显式 owner_id 过滤」与「数据范围 scope」合成最终 owner 约束（scope 为硬边界）。

    返回 None=不过滤、list=仅这些 owner、[]=无可见数据。
    """
    if scope is None:  # 可见全部
        return [owner_id] if owner_id else None
    if owner_id:  # 显式筛选，但不能越权（必须落在 scope 内）
        return [owner_id] if owner_id in scope else []
    return scope


async def apply_data_scope(
    query: Select,
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    model,
    biz_type: str,
) -> Select:
    """按数据范围过滤查询（商机等用，含创建人/共享/项目成员的额外可见性）。"""
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None:
        return query  # 管理员 / all：不限

    user_id = user.get("sub", "")
    conditions = []

    # 1. owner 在可见范围内（self=本人、dept=部门子树成员）
    if hasattr(model, "owner_id"):
        conditions.append(model.owner_id.in_(scope))

    # 2. 本人创建
    if hasattr(model, "created_by_id"):
        conditions.append(model.created_by_id == user_id)

    # 3. ACL 共享
    try:
        from app.domains.customer.models import AclShare
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

    # 3b. 项目成员：作为成员参与的商机可见
    try:
        if getattr(model, "__tablename__", "") == "opportunity_projects":
            from app.domains.project.models import ProjectMember
            member_pids_q = select(ProjectMember.project_id).where(
                ProjectMember.tenant_id == tenant_id,
                ProjectMember.user_id == user_id,
            )
            conditions.append(model.id.in_(member_pids_q))
    except (ImportError, Exception):
        pass

    if conditions:
        query = query.where(or_(*conditions))

    return query
