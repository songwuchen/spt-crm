"""
Data visibility scope filter.

数据可见范围由「角色的 data_scope」决定；可按模块用 scope_by_resource 覆盖。
取用户多个角色中该模块有效档位的最大一档：
  - all  : 全部租户数据（管理员、data:view_all，或有效档=all）
  - dept : 本人所在部门及其下级（线索看单据 department_id；其它模块看负责人所在部门）
  - self : 仅本人拥有的数据（默认）

有效档：`scope_by_resource.get(biz_type) or data_scope`（biz_type 为空则只用 data_scope）。

`resolve_owner_scope` 返回可见 owner_id 列表（None 表示不限）。
`apply_data_scope` 在 owner 范围之外，额外并入「创建人/共享/项目成员」等可见性（用于商机）。
线索部门档：以单据 `department_id` 落在本人组织部门子树为准，不按负责人兼职部门放大，
也不因「创建人」把其它事业部的单带进来（无部门的单仍可见创建人）；
草稿（review_status=draft）仅负责人/创建人/报备人可见，即使 data_scope=all 也不放开。

列表之外还必须守住「单对象」入口：`assert_in_scope` / `assert_project_child_in_scope`
是 `apply_data_scope` / `apply_project_child_scope` 的单行版本，判定口径必须与列表一致，
否则会出现「列表查不到、按 id 却读得到」的越权（详情 IDOR）。所有 update/delete 都经由
各域的 get_X() 取对象，因此在 get_X() 里带上 user 即可同时守住读与写两侧。
"""
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.common.dept_tree import subtree_dept_ids_select
from app.common.error_codes import FORBIDDEN
from app.common.exceptions import BusinessException

_SCOPE_RANK = {"self": 0, "dept": 1, "all": 2}
_VALID_SCOPES = frozenset(_SCOPE_RANK)


def _is_admin(user: dict) -> bool:
    perms = user.get("permissions", [])
    roles = user.get("roles", [])
    return "*" in perms or "data:view_all" in perms or "admin" in roles or "super_admin" in roles


def _effective_scope(data_scope: str | None, overrides: dict | None, biz_type: str | None) -> str:
    """单角色在指定模块上的有效档位。"""
    default = (data_scope or "self").strip() or "self"
    if default not in _VALID_SCOPES:
        default = "self"
    if not biz_type or not isinstance(overrides, dict):
        return default
    raw = overrides.get(biz_type)
    if isinstance(raw, str) and raw.strip() in _VALID_SCOPES:
        return raw.strip()
    return default


def normalize_scope_by_resource(raw: dict | None) -> dict[str, str]:
    """清洗前端提交的按模块范围；非法键/值丢弃。"""
    from app.common.data_scope_modules import SCOPE_MODULE_KEYS

    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            continue
        key = k.strip()
        if key not in SCOPE_MODULE_KEYS:
            continue
        if isinstance(v, str) and v.strip() in _VALID_SCOPES:
            out[key] = v.strip()
    return out


async def managed_department_ids(
    db: AsyncSession, tenant_id: str, user_id: str | None,
) -> list[str]:
    """用户「负责业务部门」及其下级部门 id（空列表表示未配置）。

    与组织编制 user_departments 分离：内勤挂在信息情报部，但负责的是精细筛分/
    冶金矿山等销售事业部线索。
    """
    if not user_id:
        return []
    from app.domains.organization.models import Department, UserManagedDepartment

    root_ids = list((await db.execute(
        select(UserManagedDepartment.department_id).where(
            UserManagedDepartment.user_id == user_id,
            UserManagedDepartment.tenant_id == tenant_id,
        )
    )).scalars().all())
    if not root_ids:
        return []
    paths = list((await db.execute(
        select(Department.path).where(
            Department.id.in_(root_ids), Department.tenant_id == tenant_id)
    )).scalars().all())
    child_ids = list((await db.execute(
        subtree_dept_ids_select(tenant_id, root_ids, paths)
    )).scalars().all())
    return list({*root_ids, *child_ids})


async def org_department_subtree_ids(
    db: AsyncSession, tenant_id: str, user_id: str | None,
) -> list[str]:
    """用户组织编制部门及其下级 id（user_departments，不含「负责业务部门」）。"""
    if not user_id or not tenant_id:
        return []
    from app.domains.organization.models import Department, UserDepartment

    my_dept_ids = list((await db.execute(
        select(UserDepartment.department_id).where(
            UserDepartment.user_id == user_id,
            UserDepartment.tenant_id == tenant_id,
        )
    )).scalars().all())
    if not my_dept_ids:
        return []
    my_paths = list((await db.execute(
        select(Department.path).where(
            Department.id.in_(my_dept_ids), Department.tenant_id == tenant_id)
    )).scalars().all())
    child_ids = list((await db.execute(
        subtree_dept_ids_select(tenant_id, my_dept_ids, my_paths)
    )).scalars().all())
    return list({*my_dept_ids, *child_ids})


async def resolve_module_scope(
    db: AsyncSession,
    user: dict,
    tenant_id: str | None = None,
    *,
    biz_type: str | None = None,
) -> str:
    """当前用户在该模块上的有效档：all / dept / self。"""
    if _is_admin(user):
        return "all"
    uid = user.get("sub")
    tid = tenant_id or user.get("tenant_id")
    if not uid:
        return "all"

    from app.domains.auth.models import Role, UserRole

    rows = (await db.execute(
        select(Role.data_scope, Role.scope_by_resource)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == uid, UserRole.tenant_id == tid)
    )).all()
    scopes: set[str] = set()
    for data_scope, overrides in rows:
        scopes.add(_effective_scope(data_scope, overrides, biz_type))
    if "all" in scopes:
        return "all"
    if "dept" in scopes:
        return "dept"
    return "self"


def lead_draft_privacy_clause(model, user_id: str | None):
    """草稿线索隐私：仅负责人 / 创建人 / 报备人可见（对 data_scope=all 同样生效）。

    报备人即业务员，与负责人同属「本单当事人」。
    非草稿 / review_status 为空：不额外限制。
    返回 SQLAlchemy 条件；user_id 为空时只能看非草稿
    （用 is_distinct_from 表达）。
    """
    if not hasattr(model, "review_status"):
        return None
    mine = []
    if hasattr(model, "owner_id"):
        mine.append(model.owner_id == user_id)
    if hasattr(model, "created_by_id"):
        mine.append(model.created_by_id == user_id)
    if hasattr(model, "reporter_id"):
        mine.append(model.reporter_id == user_id)
    if not mine or not user_id:
        # 无身份：只能看非草稿
        return model.review_status.is_distinct_from("draft")
    return or_(
        model.review_status.is_distinct_from("draft"),
        *mine,
    )


def _lead_draft_is_mine(obj, user_id: str | None) -> bool:
    """单对象：草稿是否属于当前用户（负责人 / 创建人 / 报备人）。"""
    if not user_id:
        return False
    if getattr(obj, "owner_id", None) == user_id:
        return True
    if getattr(obj, "created_by_id", None) == user_id:
        return True
    if getattr(obj, "reporter_id", None) == user_id:
        return True
    return False


async def resolve_owner_scope(
    db: AsyncSession,
    user: dict,
    tenant_id: str | None = None,
    *,
    biz_type: str | None = None,
) -> list[str] | None:
    """返回当前用户可见数据的 owner_id 集合；None 表示不限（可见全部）。

    biz_type: 业务模块（customer/lead/project…）。有值时按该模块的
    scope_by_resource 覆盖解析；为空则只用角色默认 data_scope。
    """
    if _is_admin(user):
        return None
    uid = user.get("sub")
    tid = tenant_id or user.get("tenant_id")
    if not uid:
        return None

    from app.domains.auth.models import Role, UserRole
    from app.domains.organization.models import UserDepartment

    rows = (await db.execute(
        select(Role.data_scope, Role.scope_by_resource)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == uid, UserRole.tenant_id == tid)
    )).all()

    scopes: set[str] = set()
    for data_scope, overrides in rows:
        scopes.add(_effective_scope(data_scope, overrides, biz_type))

    if "all" in scopes:
        return None
    if "dept" in scopes:
        subtree_ids = await org_department_subtree_ids(db, tid, uid)
        if subtree_ids:
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
    *,
    biz_type: str = "project",
) -> tuple[Select, Select]:
    """按「所属商机的归属」过滤商机子实体列表（报价/合同/方案/变更/交付/回款等，需有 project_id 列）。

    可见条件：父商机 owner 落在「本模块」数据范围内，或该行由本人创建 / 指派给本人，
    或父商机共享给我 / 我是项目成员。
    biz_type：子模块键（quote/contract/…）；未覆盖时仍走角色默认 data_scope。
    管理员 / 有效档=all（resolve_owner_scope 返回 None）不受限。
    返回 (query, count_query)，两者同步加上过滤条件。
    """
    scope = await resolve_owner_scope(db, user, tenant_id, biz_type=biz_type)
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
    # 无商机的外部合同：按 customer_id 数据范围可见
    if hasattr(model, "customer_id"):
        try:
            cust_ids = await visible_customer_ids_select(db, tenant_id, user)
            if cust_ids is None:
                # 管理员已在上方返回；此处 scope 非 None，用可见客户集
                pass
            else:
                conds.append(model.customer_id.in_(cust_ids))
        except Exception:
            pass
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
    scope = await resolve_owner_scope(db, user, tenant_id, biz_type="customer")
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


async def visible_project_ids_select(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
):
    """可见商机 id 的子查询；None 表示不限。口径同 apply_data_scope(OpportunityProject)。"""
    scope = await resolve_owner_scope(db, user, tenant_id, biz_type="project")
    if scope is None:
        return None

    from app.domains.project.models import OpportunityProject
    uid = user.get("sub", "")
    conds = [
        OpportunityProject.owner_id.in_(scope),
        OpportunityProject.created_by_id == uid,
    ]
    try:
        from app.domains.customer.models import AclShare
        conds.append(OpportunityProject.id.in_(select(AclShare.biz_id).where(
            AclShare.tenant_id == tenant_id,
            AclShare.biz_type == "project",
            or_(AclShare.shared_to_id == uid, AclShare.shared_to_type == "all"),
        )))
    except Exception:
        pass
    try:
        from app.domains.project.models import ProjectMember
        conds.append(OpportunityProject.id.in_(select(ProjectMember.project_id).where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.user_id == uid,
        )))
    except Exception:
        pass

    return select(OpportunityProject.id).where(
        OpportunityProject.tenant_id == tenant_id,
        or_(*conds),
    )


async def service_ticket_scope_clause(db: AsyncSession, tenant_id: str, user: dict):
    """售后工单的可见条件；None 表示不限。

    工单不像客户/商机那样有 owner_id，但它有 customer_id / project_id / assigned_to_id /
    created_by_id 四个归属维度，并不是「无归属」——按 tenant 全表放开会把全公司的故障描述、
    客户名和满意度评价摊给每个销售。

    这里必须把「指派给我」和「未分配」并进来：售后工程师(service_engineer)的 data_scope 是
    self，而客户归销售所有，只按父对象判定会让工程师看不见自己手上的工单；未分配工单相当于
    工单池（同公海客户的处理），否则新工单没人认领得到。
    """
    scope = await resolve_owner_scope(db, user, tenant_id, biz_type="service")
    if scope is None:
        return None

    from app.domains.service_ticket.models import ServiceTicket
    conds = [
        ServiceTicket.assigned_to_id.in_(scope),      # 指派给我 / 本部门成员
        ServiceTicket.created_by_id.in_(scope),       # 我报的单
    ]
    # 未分配工单池：只开给「能处理工单的人」(service:edit)，不是所有能看工单的人。
    # 实际数据里绝大多数工单 assigned_to_id 为空，若只按 service:view 放开，
    # 这一条会把几乎全部工单重新泄露出去，等于没修。
    perms = user.get("permissions", []) or []
    if "*" in perms or "service:edit" in perms:
        conds.append(ServiceTicket.assigned_to_id.is_(None))
    cust_ids = await visible_customer_ids_select(db, tenant_id, user)
    if cust_ids is not None:
        conds.append(ServiceTicket.customer_id.in_(cust_ids))
    proj_ids = await visible_project_ids_select(db, tenant_id, user)
    if proj_ids is not None:
        conds.append(ServiceTicket.project_id.in_(proj_ids))
    return or_(*conds)


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

    线索部门档以单据 department_id 为准（组织部门子树 + 负责业务部门），不因负责人
    兼职本部门而放大。草稿（review_status=draft）仅负责人/创建人/报备人可见，即使
    data_scope=all 也不放开。
    """
    if obj is None:
        return False

    # 草稿隐私优先于 all 范围放行
    if biz_type == "lead" or getattr(obj, "__tablename__", "") == "leads":
        if getattr(obj, "review_status", None) == "draft":
            return _lead_draft_is_mine(obj, user.get("sub"))

    scope = await resolve_owner_scope(db, user, tenant_id, biz_type=biz_type)
    if scope is None:  # 管理员 / 该模块有效档=all
        return True

    uid = user.get("sub", "")
    is_lead = biz_type == "lead" or getattr(obj, "__tablename__", "") == "leads"

    # 公海：无人负责的客户对全员可见（领取入口依赖于此）
    if getattr(obj, "status", None) == "pool":
        return True

    owner_id = getattr(obj, "owner_id", None)
    # 线索部门档不以「负责人兼职部门」放大；只认本人负责 / 单据上的部门
    if is_lead:
        if uid and owner_id == uid:
            return True
    elif owner_id is not None and owner_id in scope:
        return True
    if uid and getattr(obj, "created_by_id", None) == uid:
        # 线索已填部门时，创建人不能跨事业部放大（内勤代录仍属单据部门）
        if not is_lead or not getattr(obj, "department_id", None):
            return True
    # 线索报备人 = 业务员，与负责人同权可见（转商机确认待办常派给 reporter）
    if uid and (biz_type == "lead" or getattr(obj, "__tablename__", "") == "leads"):
        if getattr(obj, "reporter_id", None) == uid:
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

    # 线索：以单据 department_id 为准（组织部门子树 + 负责业务部门），不看负责人挂了哪些部门
    if is_lead:
        dept_id = getattr(obj, "department_id", None)
        if dept_id and uid:
            managed = await managed_department_ids(db, tenant_id, uid)
            if dept_id in managed:
                return True
            if await resolve_module_scope(db, user, tenant_id, biz_type="lead") == "dept":
                org_depts = await org_department_subtree_ids(db, tenant_id, uid)
                if dept_id in org_depts:
                    return True

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
    *,
    biz_type: str = "project",
) -> None:
    """商机子实体（报价/合同/方案/变更/交付/回款…）的单对象校验。

    与 `apply_project_child_scope` 同口径：父商机 owner 落在本模块范围内，
    或本行由本人创建/指派，或父商机共享/项目成员。
    """
    if user is None or obj is None:
        return
    scope = await resolve_owner_scope(db, user, tenant_id, biz_type=biz_type)
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
        if parent is not None:
            if getattr(parent, "owner_id", None) in scope:
                return
            # ACL 共享 / 项目成员仍按商机协作关系放开（与列表 apply_project_child_scope 一致）
            if uid and await _project_shared_or_member(db, tenant_id, uid, project_id):
                return

    # 无商机的外部合同：客户在可见范围内即可
    customer_id = getattr(obj, "customer_id", None)
    if customer_id:
        from app.domains.customer.models import Customer
        cust = (await db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if cust is not None and await is_in_scope(db, tenant_id, user, cust, "customer"):
            return

    raise BusinessException(code=FORBIDDEN, message=f"无权访问{label}（不在您的数据范围内）")


async def _project_shared_or_member(
    db: AsyncSession, tenant_id: str, uid: str, project_id: str,
) -> bool:
    try:
        from app.domains.customer.models import AclShare
        shared = (await db.execute(
            select(AclShare.id).where(
                AclShare.tenant_id == tenant_id,
                AclShare.biz_type == "project",
                AclShare.biz_id == project_id,
                or_(AclShare.shared_to_id == uid, AclShare.shared_to_type == "all"),
            ).limit(1)
        )).scalar_one_or_none()
        if shared is not None:
            return True
    except Exception:
        pass
    try:
        from app.domains.project.models import ProjectMember
        mem = (await db.execute(
            select(ProjectMember.id).where(
                ProjectMember.tenant_id == tenant_id,
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == uid,
            ).limit(1)
        )).scalar_one_or_none()
        if mem is not None:
            return True
    except Exception:
        pass
    return False


async def apply_data_scope(
    query: Select,
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    model,
    biz_type: str,
) -> Select:
    """按数据范围过滤查询（商机等用，含创建人/共享/项目成员的额外可见性）。

    线索：部门档以单据 department_id 落在本人组织部门子树为准，不按负责人兼职部门放大；
    已填部门的线索不以创建人跨事业部放大。
    线索草稿始终仅负责人/创建人/报备人可见，不受 data_scope=all 放开。
    """
    scope = await resolve_owner_scope(db, user, tenant_id, biz_type=biz_type)
    user_id = user.get("sub", "")
    is_lead = biz_type == "lead" or getattr(model, "__tablename__", "") == "leads"

    if scope is not None:
        conditions = []

        # 1. owner：线索只认本人负责；其它模块仍按部门成员 owner 集合
        if hasattr(model, "owner_id"):
            if is_lead:
                conditions.append(model.owner_id == user_id)
            else:
                conditions.append(model.owner_id.in_(scope))

        # 2. 本人创建：线索已填部门时不以创建人跨事业部放大
        if hasattr(model, "created_by_id"):
            if is_lead:
                conditions.append(and_(
                    model.created_by_id == user_id,
                    model.department_id.is_(None),
                ))
            else:
                conditions.append(model.created_by_id == user_id)

        # 2b. 线索报备人（业务员）
        if is_lead and hasattr(model, "reporter_id") and user_id:
            conditions.append(model.reporter_id == user_id)

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

        # 4. 线索：单据部门 ∈ 组织部门子树（dept 档）或负责业务部门
        if is_lead and hasattr(model, "department_id") and user_id:
            dept_ids: list[str] = []
            managed = await managed_department_ids(db, tenant_id, user_id)
            dept_ids.extend(managed or [])
            if await resolve_module_scope(db, user, tenant_id, biz_type="lead") == "dept":
                dept_ids.extend(await org_department_subtree_ids(db, tenant_id, user_id))
            if dept_ids:
                conditions.append(model.department_id.in_(list(set(dept_ids))))

        if conditions:
            query = query.where(or_(*conditions))

    # 草稿隐私：对 all / dept / self 一律生效
    if biz_type == "lead":
        draft_clause = lead_draft_privacy_clause(model, user_id)
        if draft_clause is not None:
            query = query.where(draft_clause)

    return query
