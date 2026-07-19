"""
Data visibility scope filter.

数据可见范围由「角色的 data_scope」决定（取用户多个角色中最大的一档）：
  - all  : 全部租户数据（管理员、data:view_all，或任一角色 data_scope=all）
  - dept : 本人所在部门及其所有下级部门的成员所拥有的数据
  - self : 仅本人拥有的数据（默认）

`resolve_owner_scope` 返回可见 owner_id 列表（None 表示不限）。
`apply_data_scope` 在 owner 范围之外，额外并入「创建人/共享/项目成员」等可见性（用于商机）。

列表之外还必须守住「单对象」入口：`assert_in_scope` / `assert_project_child_in_scope`
是 `apply_data_scope` / `apply_project_child_scope` 的单行版本，判定口径必须与列表一致，
否则会出现「列表查不到、按 id 却读得到」的越权（详情 IDOR）。所有 update/delete 都经由
各域的 get_X() 取对象，因此在 get_X() 里带上 user 即可同时守住读与写两侧。
"""
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.common.dept_tree import subtree_dept_ids_select
from app.common.error_codes import FORBIDDEN
from app.common.exceptions import BusinessException


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
            # 子树（含本部门）：统一走 dept_tree 助手，内含空路径/LIKE 元字符/结尾斜杠防御
            subtree_ids = set(my_dept_ids) | set((await db.execute(
                subtree_dept_ids_select(tid, my_dept_ids, my_paths)
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


async def apply_project_child_scope(
    query: Select,
    count_query: Select,
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    model,
) -> tuple[Select, Select]:
    """按「所属商机的归属」过滤商机子实体列表（报价/合同/方案/变更/交付/回款等，需有 project_id 列）。

    可见条件：父商机 owner 落在数据范围内，或该行由本人创建 / 指派给本人。
    管理员 / data_scope=all（resolve_owner_scope 返回 None）不受限。
    返回 (query, count_query)，两者同步加上过滤条件。
    """
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None:
        return query, count_query

    from app.domains.project.models import OpportunityProject
    uid = user.get("sub", "")
    owned_pids = select(OpportunityProject.id).where(
        OpportunityProject.tenant_id == tenant_id,
        OpportunityProject.owner_id.in_(scope),
    )
    conds = [model.project_id.in_(owned_pids)]
    # 父商机「可见」不止「归属」：共享给我 / 我是项目成员的商机，其子实体同样应可见。
    # 这里必须与 assert_project_child_in_scope 同口径，否则又会出现列表与详情不一致。
    try:
        from app.domains.customer.models import AclShare
        shared_pids = select(AclShare.biz_id).where(
            AclShare.tenant_id == tenant_id,
            AclShare.biz_type == "project",
            or_(AclShare.shared_to_id == uid, AclShare.shared_to_type == "all"),
        )
        conds.append(model.project_id.in_(shared_pids))
    except Exception:
        pass
    try:
        from app.domains.project.models import ProjectMember
        member_pids = select(ProjectMember.project_id).where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.user_id == uid,
        )
        conds.append(model.project_id.in_(member_pids))
    except Exception:
        pass
    if hasattr(model, "created_by_id"):
        conds.append(model.created_by_id == uid)
    if hasattr(model, "assignee_id"):
        conds.append(model.assignee_id == uid)
    clause = or_(*conds)
    return query.where(clause), count_query.where(clause)


async def visible_customer_ids_select(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
):
    """可见客户 id 的子查询；None 表示不限（管理员 / data_scope=all）。

    给「本身没有 owner_id、只能靠父客户判定可见性」的实体用（联系人等）。
    口径与 apply_data_scope(Customer) 对齐：归属在范围内 / 本人创建 / 共享给我 / 公海。
    """
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None:
        return None

    from app.domains.customer.models import Customer
    uid = user.get("sub", "")
    conds = [
        Customer.owner_id.in_(scope),
        Customer.status == "pool",
    ]
    if hasattr(Customer, "created_by_id"):
        conds.append(Customer.created_by_id == uid)
    try:
        from app.domains.customer.models import AclShare
        shared = select(AclShare.biz_id).where(
            AclShare.tenant_id == tenant_id,
            AclShare.biz_type == "customer",
            or_(AclShare.shared_to_id == uid, AclShare.shared_to_type == "all"),
        )
        conds.append(Customer.id.in_(shared))
    except Exception:
        pass

    return select(Customer.id).where(
        Customer.tenant_id == tenant_id,
        Customer.is_deleted == False,  # noqa: E712
        or_(*conds),
    )


async def is_in_scope(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    obj,
    biz_type: str | None = None,
) -> bool:
    """单个对象是否落在当前用户的数据可见范围内。

    判定口径与 `apply_data_scope` 保持一致：owner 在范围内 / 本人创建 / 指派给本人 /
    ACL 共享 / （商机）本人是项目成员。另外「公海」记录（status='pool'，无归属）对全员开放，
    否则 客户公海 页面会整个失效。
    """
    if obj is None:
        return False
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None:  # 管理员 / data_scope=all
        return True

    uid = user.get("sub", "")

    # 公海：无人负责的客户对全员可见（领取入口依赖于此）
    if getattr(obj, "status", None) == "pool":
        return True

    owner_id = getattr(obj, "owner_id", None)
    if owner_id is not None and owner_id in scope:
        return True
    if uid and getattr(obj, "created_by_id", None) == uid:
        return True
    if uid and getattr(obj, "assignee_id", None) == uid:
        return True

    # ACL 共享
    if biz_type:
        try:
            from app.domains.customer.models import AclShare
            shared = (await db.execute(
                select(AclShare.id).where(
                    AclShare.tenant_id == tenant_id,
                    AclShare.biz_type == biz_type,
                    AclShare.biz_id == obj.id,
                    or_(
                        AclShare.shared_to_id == uid,
                        AclShare.shared_to_type == "all",
                    ),
                ).limit(1)
            )).scalar_one_or_none()
            if shared:
                return True
        except Exception:
            pass

    # 项目成员：作为成员参与的商机可见
    try:
        if getattr(obj, "__tablename__", "") == "opportunity_projects":
            from app.domains.project.models import ProjectMember
            member = (await db.execute(
                select(ProjectMember.id).where(
                    ProjectMember.tenant_id == tenant_id,
                    ProjectMember.project_id == obj.id,
                    ProjectMember.user_id == uid,
                ).limit(1)
            )).scalar_one_or_none()
            if member:
                return True
    except Exception:
        pass

    return False


async def assert_in_scope(
    db: AsyncSession,
    tenant_id: str,
    user: dict | None,
    obj,
    biz_type: str | None = None,
    label: str = "该数据",
) -> None:
    """越权即抛 403。user 为 None 时不校验——留给审批引擎/通知等内部调用。

    内部调用（审批流读取被审业务对象、导出任务、定时提醒等）本就不代表某个登录用户的视角，
    传 None 显式表达「这次是系统在读」，避免为了绕过校验而去伪造 user。
    """
    if user is None:
        return
    if not await is_in_scope(db, tenant_id, user, obj, biz_type):
        raise BusinessException(code=FORBIDDEN, message=f"无权访问{label}（不在您的数据范围内）")


async def assert_project_child_in_scope(
    db: AsyncSession,
    tenant_id: str,
    user: dict | None,
    obj,
    label: str = "该数据",
) -> None:
    """商机子实体（报价/合同/方案/变更/交付/回款…）的单对象校验。

    与 `apply_project_child_scope` 同口径：父商机 owner 在范围内，或本行由本人创建/指派给本人。
    """
    if user is None or obj is None:
        return
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None:
        return

    uid = user.get("sub", "")
    if uid and getattr(obj, "created_by_id", None) == uid:
        return
    if uid and getattr(obj, "assignee_id", None) == uid:
        return

    project_id = getattr(obj, "project_id", None)
    if project_id:
        from app.domains.project.models import OpportunityProject
        parent = (await db.execute(
            select(OpportunityProject).where(
                OpportunityProject.id == project_id,
                OpportunityProject.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        # 父商机自身的可见性（含 ACL 共享 / 项目成员）决定子实体可见性
        if parent is not None and await is_in_scope(db, tenant_id, user, parent, "project"):
            return

    raise BusinessException(code=FORBIDDEN, message=f"无权访问{label}（不在您的数据范围内）")


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
