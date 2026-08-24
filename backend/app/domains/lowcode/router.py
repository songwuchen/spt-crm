"""扩展平台 — 表单引擎 API。

路由前缀 /api/v1/lc。权限:
- 表单模板设计/管理: form:view / form:manage
- 表单数据填报/查看: form_data:view / form_data:create / form_data:edit / form_data:delete
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
import re
import re

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions, get_data_scope
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.common.error_codes import VALIDATION_ERROR, NOT_FOUND, FORBIDDEN
from app.common.export import build_excel_multi, excel_response
from app.domains.lowcode import schemas, service

router = APIRouter(prefix="/api/v1/lc", tags=["扩展平台-表单引擎"])

# 允许配置扩展字段的既有业务实体
ENTITY_TYPES = {
    "customer", "project", "lead", "contact", "service_ticket", "order",
    "contract", "contract_review", "tech_agreement_review", "quote", "payment", "solution",
}


# ==================== 人员/部门选择器(任意登录用户可用) ====================
# 表单人员/部门字段、审批人指定人员等选择器都需要用户/部门列表；原先走 admin 接口
# (需 user:view / dept:view),导致非管理员选不了人/部门。这里提供仅需登录的轻量选择接口。

@router.get("/pickable-users")
async def pickable_users(
    keyword: str = Query(None),
    ids: str | None = Query(None, description="逗号分隔的用户 id，用于回显未落在默认列表中的人选"),
    usernames: str | None = Query(None, description="逗号分隔的 username，同上"),
    role_codes: str | None = Query(
        None,
        description="逗号分隔的角色 code（兼容旧配置）",
    ),
    scope_code: str | None = Query(None, description="可选范围编码（优先于 role_codes）"),
    range_dept_ids: str | None = Query(
        None,
        description="逗号分隔的部门 id：作为固定部门范围（与 role_codes 取并集）",
    ),
    include_children: str | None = Query(
        None,
        description="range_dept_ids 是否含下级，默认 1；传 0 关闭",
    ),
    dept_ids: str | None = Query(
        None,
        description="逗号分隔的部门 id；在范围结果上再收窄（表单科室联动）",
    ),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    from app.domains.auth.models import User, Role, UserRole
    from app.domains.organization import pickable_scope_service as pss

    extra_depts = [x.strip() for x in (dept_ids or "").split(",") if x.strip()]
    range_depts = [x.strip() for x in (range_dept_ids or "").split(",") if x.strip()]
    kids = (include_children or "1").strip() not in ("0", "false", "False", "no")
    scoped_uids: set[str] | None = None

    if scope_code:
        await pss.ensure_preset_scopes(db, tenant_id)
        await db.commit()
        scope = await pss.get_scope_by_code(db, tenant_id, scope_code.strip())
        if not scope or scope.kind != "person":
            return ok([])
        scoped_uids = await pss.resolve_person_ids(db, tenant_id, scope, extra_dept_ids=extra_depts or None)
    else:
        codes = [c.strip() for c in (role_codes or "").split(",") if c.strip()]
        parts: list[set[str]] = []
        if codes:
            from app.common.rbac_sync import ensure_business_roles, ensure_transfer_packaging_role_members
            need_ensure = [c for c in codes if c in ("room_leader", "transfer_packaging")]
            if need_ensure:
                if "room_leader" in need_ensure:
                    created = await ensure_business_roles(db, tenant_id, ["room_leader"])
                    if created:
                        await db.commit()
                if "transfer_packaging" in need_ensure:
                    await ensure_transfer_packaging_role_members(db, tenant_id)
                    await db.commit()
            role_ids = (
                await db.execute(
                    select(Role.id).where(Role.tenant_id == tenant_id, Role.code.in_(codes))
                )
            ).scalars().all()
            if role_ids:
                parts.append(set(
                    (
                        await db.execute(
                            select(UserRole.user_id).where(
                                UserRole.tenant_id == tenant_id, UserRole.role_id.in_(role_ids),
                            )
                        )
                    ).scalars().all()
                ))
            else:
                parts.append(set())
        if range_depts:
            parts.append(await pss._user_ids_in_depts(db, tenant_id, range_depts, kids))
        if parts:
            scoped_uids = set()
            for p in parts:
                scoped_uids |= p
        elif extra_depts:
            scoped_uids = await pss._user_ids_in_depts(db, tenant_id, extra_depts, True)

        if scoped_uids is not None and extra_depts and (codes or range_depts):
            in_dept = await pss._user_ids_in_depts(db, tenant_id, extra_depts, True)
            scoped_uids &= in_dept

    q = select(User.id, User.real_name, User.username).where(
        User.tenant_id == tenant_id, User.is_active == True,  # noqa: E712
    )
    if scoped_uids is not None:
        if not scoped_uids:
            return ok([])
        q = q.where(User.id.in_(scoped_uids))

    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(User.real_name.ilike(like), User.username.ilike(like)))
    rows = (await db.execute(q.order_by(User.real_name).limit(5000))).all()
    by_id = {r[0]: r for r in rows}
    extra_ids = [x.strip() for x in (ids or "").split(",") if x.strip()]
    extra_names = [x.strip() for x in (usernames or "").split(",") if x.strip()]
    missing_ids = [i for i in extra_ids if i not in by_id]
    missing_names = extra_names
    if missing_ids or missing_names:
        conds = []
        if missing_ids:
            conds.append(User.id.in_(missing_ids))
        if missing_names:
            conds.append(User.username.in_(missing_names))
        extra = (await db.execute(
            select(User.id, User.real_name, User.username).where(
                User.tenant_id == tenant_id, or_(*conds),
            )
        )).all()
        for r in extra:
            by_id[r[0]] = r
    from app.domains.organization.pickable_scope_service import department_names_by_user_ids

    dept_map = await department_names_by_user_ids(db, tenant_id, list(by_id.keys()))
    out = [
        {
            "id": r[0],
            "name": r[1] or r[2],
            "username": r[2],
            "departments": dept_map.get(r[0], []),
        }
        for r in sorted(by_id.values(), key=lambda x: (x[1] or x[2] or ""))
    ]
    return ok(out)


@router.get("/department-labels")
async def department_labels(
    ids: str = Query(..., description="逗号分隔的部门 id（CRM UUID 或简道云 MongoId）"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """回显部门名称：先查 CRM，再兜底简道云 id→名称（流程条件历史值）。"""
    from app.domains.organization.models import Department
    from app.domains.lowcode.jdy_id_remap import jdy_dept_id_to_name

    raw = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not raw:
        return ok({})
    rows = (
        await db.execute(
            select(Department.id, Department.name).where(
                Department.tenant_id == tenant_id,
                Department.id.in_(raw),
            )
        )
    ).all()
    out = {str(i): (n or str(i)) for i, n in rows}
    jdy_names = jdy_dept_id_to_name()
    for i in raw:
        if i not in out and i in jdy_names:
            out[i] = jdy_names[i]
    return ok(out)


@router.get("/person-labels")
async def person_labels(
    ids: str = Query(..., description="逗号分隔的用户 id（CRM UUID 或简道云 MongoId）"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """回显人员姓名：先查 CRM，再按简道云 id→姓名 / id→CRM 映射兜底（流程条件历史值）。"""
    from app.domains.auth.models import User
    from app.domains.lowcode.jdy_id_remap import (
        build_jdy_to_crm_user_map,
        is_jdy_mongo_id,
        jdy_person_id_to_name,
    )

    raw = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not raw:
        return ok({})
    jdy_to_crm = await build_jdy_to_crm_user_map(db, tenant_id)
    crm_ids = set(raw)
    for jid in raw:
        if is_jdy_mongo_id(jid) and jid in jdy_to_crm:
            crm_ids.add(jdy_to_crm[jid])
    rows = (
        await db.execute(
            select(User.id, User.real_name, User.username).where(
                User.tenant_id == tenant_id,
                User.id.in_(list(crm_ids)),
            )
        )
    ).all()
    crm_names = {str(i): (n or u or str(i)) for i, n, u in rows}
    out: dict[str, str] = {}
    for i in raw:
        if i in crm_names:
            out[i] = crm_names[i]
            continue
        if is_jdy_mongo_id(i):
            cid = jdy_to_crm.get(i)
            if cid and cid in crm_names:
                out[i] = crm_names[cid]
                continue
    jdy_names = jdy_person_id_to_name()
    for i in raw:
        if i not in out and i in jdy_names:
            out[i] = jdy_names[i]
    return ok(out)


@router.get("/department-code")
async def lookup_department_code(
    department_id: str = Query(..., description="CRM 部门 id"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """按部门 id 查「部门编号基础表」编号，供方案/安装图表单回填。"""
    from app.domains.lowcode.dept_code import resolve_dept_code

    code = await resolve_dept_code(db, tenant_id, department_id, user)
    return ok({"department_id": department_id, "dept_code": code})


@router.get("/salesperson-region")
async def lookup_salesperson_region(
    salesperson_id: str = Query(..., description="业务员用户 id"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """按业务员查「业务员区域经理对照」表，供合同评审/客服等回填区域经理。"""
    from app.domains.lowcode.salesperson_region import resolve_region_manager

    data = await resolve_region_manager(db, tenant_id, salesperson_id, user)
    return ok(data)


@router.get("/base-lookups")
async def base_form_lookups(
    type: str = Query(..., description="application_field | application_material | material_name"),
    keyword: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """基础资料选项（本库物料名称 / 应用领域 / 应用物料）。"""
    from app.domains.lowcode.base_lookups import list_base_form_lookups

    items = await list_base_form_lookups(
        db, tenant_id, user, form_code=type, keyword=keyword, limit=limit,
    )
    return ok(items)


@router.get("/pickable-roles")
async def pickable_roles(
    keyword: str = Query(None, description="按角色中文名或编码筛选"),
    codes: str | None = Query(None, description="逗号分隔的角色 code，用于回显"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """流程设计器选角色：返回角色中文名 + 成员数（无需 role:view）。"""
    from app.domains.organization import service as org_svc
    from app.common.rbac_sync import ensure_nine_flow_role_members

    await ensure_nine_flow_role_members(db, tenant_id)
    await db.commit()

    roles = await org_svc.list_roles(db, tenant_id)
    counts = await org_svc.count_role_members(db, tenant_id, [r.id for r in roles])
    want_codes = {c.strip() for c in (codes or "").split(",") if c.strip()}
    kw = (keyword or "").strip().lower()

    out = []
    for r in roles:
        if kw and kw not in (r.name or "").lower() and kw not in (r.code or "").lower():
            continue
        out.append({
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "description": r.description,
            "member_count": counts.get(r.id, 0),
        })
    # 保证回显 code 即使被 keyword 滤掉也带上
    if want_codes:
        have = {x["code"] for x in out}
        for r in roles:
            if r.code in want_codes and r.code not in have:
                out.insert(0, {
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "description": r.description,
                    "member_count": counts.get(r.id, 0),
                })
    out.sort(key=lambda x: ((x.get("name") or x["code"]), x["code"]))
    return ok(out)


@router.get("/pickable-departments")
async def pickable_departments(
    scope_code: str | None = Query(None, description="可选范围编码（department 类型）"),
    dept_ids: str | None = Query(
        None,
        description="逗号分隔的部门 id：直接限定可选部门树（与 scope_code 二选一）",
    ),
    include_children: str | None = Query(
        None,
        description="dept_ids 是否含下级，默认 1；传 0 关闭",
    ),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    from app.domains.organization.service import get_department_tree
    from app.domains.organization import pickable_scope_service as pss

    tree = await get_department_tree(db, tenant_id)
    allowed: set[str] | None = None
    if scope_code:
        await pss.ensure_preset_scopes(db, tenant_id)
        await db.commit()
        scope = await pss.get_scope_by_code(db, tenant_id, scope_code.strip())
        if not scope or scope.kind != "department":
            return ok([])
        allowed = await pss.resolve_department_ids(db, tenant_id, scope)
    else:
        roots = [x.strip() for x in (dept_ids or "").split(",") if x.strip()]
        if roots:
            kids = (include_children or "1").strip() not in ("0", "false", "False", "no")
            allowed = await pss.resolve_department_ids(
                db, tenant_id,
                {"kind": "department", "rules": {"dept_ids": roots, "include_children": kids}},
            )

    if allowed is None:
        return ok(tree)

    def prune(nodes: list) -> list:
        out = []
        for n in nodes or []:
            kids_nodes = prune(n.get("children") or [])
            if n.get("id") in allowed or kids_nodes:
                nn = dict(n)
                nn["children"] = kids_nodes
                # 不在允许集合内的祖先仅作展开用，仍返回（与 TreeSelect 常见行为一致）
                out.append(nn)
        return out

    return ok(prune(tree))


@router.get("/pickable-projects")
async def pickable_projects(
    keyword: str | None = Query(None),
    ids: str | None = Query(None, description="逗号分隔的商机 id，用于只读回显"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """表单/审批回显商机名称：仅需登录，不要求 project:view。"""
    from app.domains.project.models import OpportunityProject as Project

    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    q = select(Project.id, Project.name, Project.project_code).where(
        Project.tenant_id == tenant_id, Project.is_deleted == False,  # noqa: E712
    )
    if id_list:
        q = q.where(Project.id.in_(id_list))
    elif keyword:
        like = f"%{keyword}%"
        q = q.where(or_(Project.name.ilike(like), Project.project_code.ilike(like))).limit(50)
    else:
        q = q.order_by(Project.updated_at.desc()).limit(50)
    rows = (await db.execute(q)).all()
    return ok([
        {"id": r[0], "name": r[1], "project_code": r[2]}
        for r in rows
    ])


@router.get("/pickable-projects/{project_id}/install-notice-fill")
async def pickable_project_install_notice_fill(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """安装图「项目号选择」选商机后带出业务员/公司名称/事项（仅需登录）。"""
    from app.domains.project.models import OpportunityProject as Project

    p = (
        await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
                Project.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not p:
        raise BusinessException(code=NOT_FOUND, message="商机不存在")

    customer_name = None
    if p.customer_id:
        from app.common.list_enrich import customer_names_map
        names = await customer_names_map(db, tenant_id, [p.customer_id])
        customer_name = names.get(p.customer_id)
    # 迁移商机常无 customer_id，公司名在扩展字段（对齐简道云「公司名称」）
    if not (customer_name or "").strip():
        cf = p.custom_fields_json if isinstance(p.custom_fields_json, dict) else {}
        for key in ("公司名称", "company_name", "customer_name"):
            raw = cf.get(key)
            if raw is not None and str(raw).strip():
                customer_name = str(raw).strip()
                break

    fill = {
        "sales_person": p.owner_id or None,
        "customer_name": customer_name or "",
        "matter": (p.name or "").strip(),
    }
    return ok({
        "project_id": p.id,
        "project_code": p.project_code,
        "fill": fill,
    })


@router.get("/pickable-customers")
async def pickable_customers(
    keyword: str | None = Query(None),
    ids: str | None = Query(None, description="逗号分隔的客户 id，用于只读回显"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """表单/审批回显客户名称：仅需登录，不要求 customer:view。"""
    from app.domains.customer.models import Customer

    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    q = select(Customer.id, Customer.name, Customer.customer_code).where(
        Customer.tenant_id == tenant_id, Customer.is_deleted == False,  # noqa: E712
    )
    if id_list:
        q = q.where(Customer.id.in_(id_list))
    elif keyword:
        like = f"%{keyword}%"
        q = q.where(or_(Customer.name.ilike(like), Customer.customer_code.ilike(like))).limit(50)
    else:
        q = q.order_by(Customer.updated_at.desc()).limit(50)
    rows = (await db.execute(q)).all()
    return ok([
        {"id": r[0], "name": r[1], "customer_code": r[2]}
        for r in rows
    ])


@router.get("/customer-form-fill/{customer_id}")
async def customer_form_fill(
    customer_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """选客户后联动回填：客户类别（=客户信息·客户类型 A/B/C/D）、货物地址。"""
    from app.domains.customer.models import Customer

    row = (await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not row:
        return ok({})
    # 简道云 cs_product_replace「客户类别」linkquery → 客户信息「客户类型」(A/B/C/D)
    category = (row.level or "").strip() or None
    addr = {
        "province": row.province,
        "city": row.city,
        "district": row.district,
        "detail": row.address,
    }
    return ok({
        "customer_category": category,
        # 更换 field_3 / 退回 field_6 均为「货物地址」，同 jdy widget
        "field_3": addr,
        "field_6": addr,
    })


@router.get("/pickable-contracts")
async def pickable_contracts(
    keyword: str | None = Query(None),
    ids: str | None = Query(None, description="逗号分隔的合同 id，用于只读回显"),
    department_id: str | None = Query(
        None, description="按合同所属部门过滤（单部门用户或表单指定部门）",
    ),
    department_ids: str | None = Query(
        None, description="逗号分隔的部门 id；多部门编制用户选合同时并集过滤",
    ),
    purpose: str | None = Query(
        None,
        description="选合同场景：invoice_application 时不按部门收窄（开票需跨部门选合同）",
    ),
    page: int | None = Query(None, ge=1, description="传 page 时返回弹窗分页结构"),
    page_size: int = Query(20, ge=1, le=50),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """表单/审批关联合同：按图纸编号检索与回显（仅需登录，不要求 contract:view）。"""
    from app.common.data_scope import org_department_subtree_ids, resolve_module_scope
    from app.domains.contract.models import Contract
    from app.domains.lowcode.contract_pick_scope import (
        apply_contract_department_filter,
        resolve_pick_department_ids,
    )
    from sqlalchemy import case

    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    dept_id_list = [x.strip() for x in (department_ids or "").split(",") if x.strip()]
    scope = await resolve_module_scope(db, current_user, tenant_id, biz_type="contract")
    # 开票申请：市场支持等需跨「暂存」/事业部选合同，不按部门树收窄
    scope_all = scope == "all" or (purpose or "").strip() == "invoice_application"
    user_depts = await org_department_subtree_ids(db, tenant_id, current_user.get("sub"))
    pick_depts = resolve_pick_department_ids(
        scope_all=scope_all,
        user_department_ids=user_depts,
        department_id=department_id,
        department_ids=dept_id_list or None,
        for_id_lookup=bool(id_list),
    )
    if pick_depts:
        from app.common.dept_equivalence import expand_equivalent_department_ids
        pick_depts = await expand_equivalent_department_ids(db, tenant_id, pick_depts)

    if page is not None:
        from app.domains.lowcode.contract_pick import list_pickable_contracts_page
        data = await list_pickable_contracts_page(
            db, tenant_id,
            keyword=keyword, ids=id_list or None,
            department_id=department_id,
            department_ids=dept_id_list or None,
            scope_all=scope_all,
            user_department_ids=user_depts,
            page=page, page_size=page_size,
        )
        return ok(data)
    q = select(Contract.id, Contract.contract_no, Contract.drawing_no).where(
        Contract.tenant_id == tenant_id,
    )
    dept_conds: list = []
    apply_contract_department_filter(dept_conds, Contract, pick_depts)
    if dept_conds:
        q = q.where(*dept_conds)
    if id_list:
        q = q.where(Contract.id.in_(id_list))
    elif keyword:
        kw = keyword.strip()
        like = f"%{kw}%"
        # 优先命中图纸编号，其次合同号
        q = q.where(or_(
            Contract.drawing_no.ilike(like),
            Contract.contract_no.ilike(like),
            Contract.peer_contract_no.ilike(like),
        )).order_by(
            case(
                (Contract.drawing_no.ilike(like), 0),
                (Contract.contract_no.ilike(like), 1),
                else_=2,
            ),
            Contract.updated_at.desc(),
        ).limit(50)
    else:
        q = q.order_by(
            case((Contract.drawing_no.is_not(None) & (Contract.drawing_no != ""), 0), else_=1),
            Contract.updated_at.desc(),
        ).limit(50)
    rows = (await db.execute(q)).all()
    return ok([
        {"id": r[0], "contract_no": r[1], "drawing_no": r[2]}
        for r in rows
    ])


@router.get("/pickable-form-instances")
async def pickable_form_instances(
    form_code: str = Query(..., description="源表单 builtin code，如 install_drawing_notice"),
    link_field: str | None = Query(None, description="核价清单选择字段 id，用于带出映射"),
    keyword: str | None = Query(None),
    ids: str | None = Query(None, description="逗号分隔的实例 id，用于只读回显"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """表单关联选择：从另一张已发布表单选实例（仅需登录，不要求 form_data:view）。"""
    from app.domains.lowcode.pricing_checklist_fields import (
        PICKABLE_FORM_CODES, list_pickable_form_instances,
    )
    code = (form_code or "").strip()
    if code not in PICKABLE_FORM_CODES:
        raise BusinessException(code=VALIDATION_ERROR, message="不支持的关联表单")
    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    data = await list_pickable_form_instances(
        db, tenant_id, form_code=code, link_field=link_field,
        keyword=keyword, ids=id_list or None,
        page=page, page_size=page_size,
    )
    return ok(data)


@router.get("/pickable-contracts/{contract_id}/prod-card-fill")
async def pickable_contract_prod_card_fill(
    contract_id: str,
    mode: str = Query(
        "drawing_no_query",
        description="drawing_no_query / contract_no_select / invoice_application / shipment_notice",
    ),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """选合同后带出字段（生产卡 / 开票申请 / 发货通知；不要求 contract:view）。"""
    from app.domains.contract.models import Contract, ContractVersion
    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_fill_from_contract
    from app.domains.lowcode.invoice_application_fields import build_invoice_fill_from_contract
    from app.domains.lowcode.shipment_notice_fields import build_shipment_fill_from_contract

    if mode not in ("drawing_no_query", "contract_no_select", "invoice_application", "shipment_notice"):
        mode = "drawing_no_query"
    c = (
        await db.execute(
            select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not c:
        raise BusinessException(code=NOT_FOUND, message="合同不存在")

    ver = (
        await db.execute(
            select(ContractVersion).where(
                ContractVersion.tenant_id == tenant_id,
                ContractVersion.contract_id == contract_id,
                ContractVersion.version_no == c.current_version_no,
            )
        )
    ).scalar_one_or_none()
    if not ver:
        ver = (
            await db.execute(
                select(ContractVersion).where(
                    ContractVersion.tenant_id == tenant_id,
                    ContractVersion.contract_id == contract_id,
                ).order_by(ContractVersion.version_no.desc()).limit(1)
            )
        ).scalar_one_or_none()

    customer_name = None
    customer_code = None
    taxpayer_id = None
    invoice_address_phone = None
    bank_account = None
    cust_id = c.customer_id
    if not cust_id and c.project_id:
        from app.domains.project.models import OpportunityProject
        cust_id = (
            await db.execute(
                select(OpportunityProject.customer_id).where(
                    OpportunityProject.id == c.project_id,
                    OpportunityProject.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    if cust_id:
        from app.domains.customer.models import Customer
        cu = (
            await db.execute(
                select(Customer).where(Customer.id == cust_id, Customer.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if cu:
            customer_name = cu.name
            customer_code = cu.customer_code
            taxpayer_id = getattr(cu, "taxpayer_id", None)
            invoice_address_phone = getattr(cu, "invoice_address_phone", None)
            bank_account = getattr(cu, "bank_account", None)
        else:
            from app.common.list_enrich import customer_names_map
            names = await customer_names_map(db, tenant_id, [cust_id])
            customer_name = names.get(cust_id)

    # 无主数据客户时，回落到合同登记里的单位/客户名称（生产卡「单位名称」带出）
    if not (customer_name or "").strip() and isinstance(c.registration_json, dict):
        for key in ("customer_name", "company_name", "单位名称", "客户名称"):
            raw = c.registration_json.get(key)
            if raw is not None and str(raw).strip():
                customer_name = str(raw).strip()
                break

    if mode == "invoice_application":
        fill = build_invoice_fill_from_contract(
            contract_no=c.contract_no,
            drawing_no=c.drawing_no,
            peer_contract_no=c.peer_contract_no,
            assignee_id=c.assignee_id,
            customer_name=customer_name,
            customer_code=customer_code,
            amount_total=c.amount_total,
            taxpayer_id=taxpayer_id,
            invoice_address_phone=invoice_address_phone,
            bank_account=bank_account,
            key_clauses_json=ver.key_clauses_json if ver else None,
        )
        from app.domains.lowcode.invoice_application_fields import (
            list_invoice_applications_for_contract,
        )
        prior = await list_invoice_applications_for_contract(
            db, tenant_id,
            contract_id=c.id,
            contract_no=c.contract_no,
            drawing_no=c.drawing_no,
            peer_contract_no=c.peer_contract_no,
        )
        return ok({
            "contract_id": c.id,
            "contract_no": c.contract_no,
            "drawing_no": c.drawing_no,
            "department_id": c.department_id,
            "fill": fill,
            "prior_invoices": prior,
            "prior_invoice_count": len(prior),
            "prior_invoice_amount_sum": round(
                sum(x.get("total_amount") or 0 for x in prior if x.get("total_amount") is not None),
                2,
            ),
        })
    elif mode == "shipment_notice":
        from app.domains.lowcode.shipment_notice_fields import (
            sum_prior_ship_amount_for_contract,
        )
        prior_shipped = await sum_prior_ship_amount_for_contract(
            db, tenant_id,
            contract_id=c.id,
            contract_no=c.contract_no,
            drawing_no=c.drawing_no,
        )
        fill = build_shipment_fill_from_contract(
            contract_no=c.contract_no,
            drawing_no=c.drawing_no,
            peer_contract_no=c.peer_contract_no,
            assignee_id=c.assignee_id,
            department_id=c.department_id,
            customer_name=customer_name,
            amount_total=c.amount_total,
            registration_json=c.registration_json if isinstance(c.registration_json, dict) else {},
            key_clauses_json=ver.key_clauses_json if ver else None,
            prior_shipped_amount=prior_shipped,
        )
    else:
        fill = build_prod_card_fill_from_contract(
            contract_no=c.contract_no,
            drawing_no=c.drawing_no,
            assignee_id=c.assignee_id,
            assignee_name=c.assignee_name,
            customer_name=customer_name,
            delivery_date=str(c.delivery_date) if c.delivery_date else None,
            registration_json=c.registration_json if isinstance(c.registration_json, dict) else {},
            key_clauses_json=ver.key_clauses_json if ver else None,
            mode=mode,
        )
        from app.domains.lowcode.prod_card_contract_fill import enrich_prod_card_fill_with_region_manager
        fill = await enrich_prod_card_fill_with_region_manager(db, tenant_id, fill, _user)
    return ok({
        "contract_id": c.id,
        "contract_no": c.contract_no,
        "drawing_no": c.drawing_no,
        "department_id": c.department_id,
        "fill": fill,
    })


@router.get("/pickable-tech-agreement-reviews")
async def pickable_tech_agreement_reviews(
    keyword: str | None = Query(None),
    ids: str | None = Query(None, description="逗号分隔的评审 id，用于只读回显"),
    applicant_id: str | None = Query(
        None, description="申请人过滤（生产卡：提交人）；与 department_id 为 OR",
    ),
    department_id: str | None = Query(
        None, description="业务部门过滤（生产卡：所在部门）；与 applicant_id 为 OR",
    ),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """表单关联技术协议评审：按流水号/项目/公司检索（仅需登录）。"""
    from app.domains.tech_agreement_review.models import TechAgreementReview

    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    q = select(
        TechAgreementReview.id,
        TechAgreementReview.review_code,
        TechAgreementReview.company_name,
        TechAgreementReview.project_title,
        TechAgreementReview.applicant_name,
        TechAgreementReview.department_name,
    ).where(TechAgreementReview.tenant_id == tenant_id)

    if id_list:
        q = q.where(TechAgreementReview.id.in_(id_list))
    else:
        app_id = (applicant_id or "").strip()
        dept = (department_id or "").strip()
        if app_id and dept:
            q = q.where(or_(
                TechAgreementReview.applicant_id == app_id,
                TechAgreementReview.department_id == dept,
            ))
        elif app_id:
            q = q.where(TechAgreementReview.applicant_id == app_id)
        elif dept:
            q = q.where(TechAgreementReview.department_id == dept)
        if keyword:
            kw = keyword.strip()
            like = f"%{kw}%"
            q = q.where(or_(
                TechAgreementReview.review_code.ilike(like),
                TechAgreementReview.company_name.ilike(like),
                TechAgreementReview.project_title.ilike(like),
                TechAgreementReview.applicant_name.ilike(like),
            ))
        q = q.order_by(TechAgreementReview.updated_at.desc()).limit(50)

    rows = (await db.execute(q)).all()
    return ok([
        {
            "id": r[0],
            "review_code": r[1],
            "company_name": r[2],
            "project_title": r[3],
            "applicant_name": r[4],
            "department_name": r[5],
        }
        for r in rows
    ])


@router.get("/pickable-tech-agreement-reviews/{review_id}/prod-card-fill")
async def pickable_tar_prod_card_fill(
    review_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """生产卡选技术协议评审后带出流水号（对齐简道云 linkDataMaps）。"""
    from app.domains.tech_agreement_review.models import TechAgreementReview
    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_fill_from_tar

    row = (
        await db.execute(
            select(TechAgreementReview).where(
                TechAgreementReview.id == review_id,
                TechAgreementReview.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise BusinessException(code=NOT_FOUND, message="技术协议评审不存在")
    fill = build_prod_card_fill_from_tar(review_code=row.review_code)
    return ok({
        "review_id": row.id,
        "review_code": row.review_code,
        "fill": fill,
    })


# ==================== 模板序列化 ====================

def _tpl_dict(t) -> dict:
    return schemas.FormTemplateOut.model_validate(t).model_dump()


def _ver_dict(v) -> dict:
    return schemas.FormTemplateVersionOut.model_validate(v).model_dump(mode="json")


def _inst_list_dict(i, name_map: dict[str, str] | None = None) -> dict:
    d = schemas.FormInstanceListItem.model_validate(i).model_dump(mode="json")
    if name_map is not None and getattr(i, "initiator_id", None):
        d["initiator_name"] = name_map.get(i.initiator_id)
    if not d.get("initiator_name"):
        fd = d.get("form_data") or getattr(i, "form_data", None) or {}
        if isinstance(fd, dict):
            fallback = (fd.get("_jdy_creator_name") or "").strip()
            if fallback:
                d["initiator_name"] = fallback
    return d


# ==================== 表单模板 ====================

@router.get("/form-templates")
async def list_form_templates(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    name: str = Query(None),
    category: str = Query(None),
    published_only: bool = Query(False),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    items, total = await service.list_templates(
        db, tenant_id, pageNo, pageSize, name=name,
        published_only=published_only, category=category,
    )
    return ok({"items": [_tpl_dict(t) for t in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/form-templates")
async def create_form_template(
    body: schemas.FormTemplateCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    tpl = await service.create_template(db, tenant_id, body, user)
    return ok(_tpl_dict(tpl))


@router.get("/builtin-templates")
async def list_builtin_templates(
    _user=Depends(require_permissions("form:manage")),
):
    """模板市场: 列出可一键安装的内置表单模板。"""
    from app.domains.lowcode.builtin_templates import list_builtin
    return ok(list_builtin())


@router.post("/builtin-templates/{key}/install")
async def install_builtin_template(
    key: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    """从模板市场安装内置模板为本租户草稿表单，返回新模板(可继续设计/发布)。"""
    tpl = await service.install_builtin_template(db, tenant_id, key, user)
    return ok(_tpl_dict(tpl))


@router.post("/builtin-templates/{key}/ensure")
async def ensure_builtin_template(
    key: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:view")),
):
    """侧栏模块入口：按稳定 code=key 确保内置表单已安装并发布（不覆盖已有字段定制）。"""
    tpl = await service.ensure_builtin_form(db, tenant_id, key, user)
    return ok(_tpl_dict(tpl))


@router.get("/form-templates/by-code/{code}")
async def get_form_template_by_code(
    code: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    tpl = await service.get_template_by_code(db, tenant_id, code)
    if not tpl:
        raise BusinessException(code=NOT_FOUND, message="表单模板不存在")
    return ok(_tpl_dict(tpl))


@router.get("/form-templates/{template_id}")
async def get_form_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    tpl = await service.get_template(db, tenant_id, template_id)
    return ok(_tpl_dict(tpl))


@router.put("/form-templates/{template_id}")
async def update_form_template(
    template_id: str,
    body: schemas.FormTemplateUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:manage")),
):
    tpl = await service.update_template(db, tenant_id, template_id, body)
    return ok(_tpl_dict(tpl))


@router.delete("/form-templates/{template_id}")
async def delete_form_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:manage")),
):
    await service.delete_template(db, tenant_id, template_id)
    return ok(None)


# ==================== 设计 / 版本 / 发布 ====================

@router.get("/form-templates/{template_id}/design")
async def load_form_design(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    """设计器加载: 返回最新(草稿优先)版本;无版本返回空设计。

    实体扩展字段的系统模板会把该实体的原生字段(按目录重建、叠加已存覆盖项)排在前面一并
    返回，管理员因此能在同一个设计器里配置内置字段的必填/显隐/只读/字段级权限。
    """
    tpl = await service.get_template(db, tenant_id, template_id)
    version = await service.get_design(db, tenant_id, template_id)
    design = (_ver_dict(version) if version
              else {"field_definitions": [], "layout_definition": {}, "rule_definitions": []})

    from app.domains.lowcode.native_field_catalog import (
        has_native_catalog, merge_native_overrides, merge_system_rules, get_system_rules,
    )
    # is_system 这一半不能省：原生字段只属于实体扩展字段的系统模板，
    # 若某个普通表单模板也带上了 entity_type，不该凭空多出一整套内置字段
    if tpl.is_system and tpl.entity_type and has_native_catalog(tpl.entity_type):
        stored = design["field_definitions"] or []
        design["field_definitions"] = (
            merge_native_overrides(tpl.entity_type, stored)
            + [fd for fd in stored if not (isinstance(fd, dict) and fd.get("native"))]
        )
        # 系统规则可编辑：目录默认 ← 草稿覆盖；defaults 供设计器「恢复默认」
        design["system_rule_defaults"] = get_system_rules(tpl.entity_type)
        design["rule_definitions"] = merge_system_rules(
            tpl.entity_type, design.get("rule_definitions") or [],
        )
        design["entity_type"] = tpl.entity_type
        design["is_system_entity"] = True
    return ok(design)


@router.post("/form-templates/{template_id}/design")
async def save_form_design(
    template_id: str,
    body: schemas.SaveDesignRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    version = await service.save_design(db, tenant_id, template_id, body, user.get("sub"))
    return ok(_ver_dict(version))


@router.post("/form-templates/{template_id}/publish")
async def publish_form_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    version = await service.publish(db, tenant_id, template_id, user.get("sub"))
    return ok(_ver_dict(version))


@router.get("/form-templates/{template_id}/versions")
async def list_form_versions(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    versions = await service.get_versions(db, tenant_id, template_id)
    return ok([_ver_dict(v) for v in versions])


@router.get("/form-templates/{template_id}/published-version")
async def get_published_form_version(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:view")),
):
    """填报页加载已发布 schema。"""
    version = await service.get_published_version(db, tenant_id, template_id)
    return ok(_ver_dict(version))


@router.post("/form-templates/{template_id}/peek-serials")
async def peek_form_serials(
    template_id: str,
    body: schemas.PeekSerialsRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:create")),
):
    """填报页预览下一流水号（不消耗计数），对齐简道云「点添加即显示编号」。

    合同图纸对应表图纸编号：跳过本表已占用号（可推进计数空洞），不跳历史合同登记号。
    """
    from app.domains.lowcode.models import FormTemplate
    from app.domains.lowcode.serial_number import peek_serials_for_form, peek_serial_value
    from app.domains.lowcode.drawing_no_pool import peek_drawing_no_skipping_taken
    from sqlalchemy import select

    version = await service.get_published_version(db, tenant_id, template_id)
    field_defs = version.field_definitions or []
    form_data = body.form_data or {}
    tpl_code = (
        await db.execute(
            select(FormTemplate.code).where(
                FormTemplate.id == template_id,
                FormTemplate.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if tpl_code == "contract_drawing_map":
        previews: dict[str, str] = {}
        for fd in field_defs:
            fid = fd.get("id")
            if fd.get("type") != "auto_number" or not fid:
                continue
            if str(fid) == "drawing_no":
                previews[str(fid)] = await peek_drawing_no_skipping_taken(
                    db, tenant_id, template_id, fd, form_data, field_defs,
                    map_template_id=template_id,
                    map_only=True,
                )
            else:
                previews[str(fid)] = await peek_serial_value(
                    db, tenant_id, template_id, fd, form_data, field_defs,
                )
        await db.commit()  # 跳过本表已占用号时可能推进了计数空洞
        return ok(previews)
    previews = await peek_serials_for_form(
        db, tenant_id, template_id, field_defs, form_data,
    )
    return ok(previews)


@router.post("/form-templates/{template_id}/allocate-serials")
async def allocate_form_serials(
    template_id: str,
    body: schemas.AllocateSerialsRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:create")),
):
    """填报页重新取号：当前号仍可用则原样返回；否则占计数并跳过已存在编号。"""
    from app.domains.lowcode.serial_number import allocate_unique_serials
    from app.domains.lowcode.models import FormTemplate
    from app.domains.lowcode.drawing_no_pool import is_drawing_no_taken_in_map
    from sqlalchemy import select

    version = await service.get_published_version(db, tenant_id, template_id)
    field_defs = version.field_definitions or []
    form_data = dict(body.form_data or {})
    tpl_code = (
        await db.execute(
            select(FormTemplate.code).where(
                FormTemplate.id == template_id,
                FormTemplate.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()

    async def is_taken(field_id: str, value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False
        if tpl_code == "contract_drawing_map" and field_id == "drawing_no":
            # 对应表重新取号：只避开本表已占用号，不跳历史合同登记空洞
            return await is_drawing_no_taken_in_map(
                db, tenant_id, v, map_template_id=template_id,
            )
        from app.domains.lowcode.models import FormInstance
        hit = (
            await db.execute(
                select(FormInstance.id)
                .where(
                    FormInstance.tenant_id == tenant_id,
                    FormInstance.template_id == template_id,
                    FormInstance.is_deleted == False,  # noqa: E712
                    FormInstance.form_data[field_id].astext == v,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return hit is not None

    try:
        allocated = await allocate_unique_serials(
            db, tenant_id, template_id, field_defs, form_data,
            field_ids=body.field_ids,
            is_taken=is_taken,
        )
    except ValueError as e:
        raise BusinessException(code=VALIDATION_ERROR, message=str(e)) from e
    await db.commit()
    return ok(allocated)


# ==================== 实体扩展字段(统一自定义字段到表单引擎) ====================

def _check_entity(entity_type: str):
    if entity_type not in ENTITY_TYPES:
        raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的实体类型: {entity_type}")


@router.get("/entity-templates/{entity_type}")
async def get_entity_template(
    entity_type: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    """取(或创建)该业务实体的扩展字段系统模板,返回后前端跳到表单设计器为其设计字段。"""
    _check_entity(entity_type)
    tpl = await service.get_or_create_entity_template(db, tenant_id, entity_type, user)
    return ok(_tpl_dict(tpl))


@router.get("/entity-fields/{entity_type}")
async def get_entity_fields(
    entity_type: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """取该业务实体已发布的扩展字段定义与规则,供业务表单/详情页用 FormRenderer 渲染。"""
    _check_entity(entity_type)
    from app.domains.lowcode.native_field_catalog import merge_system_rules
    schema = await service.get_entity_schema(db, tenant_id, entity_type)
    # 只返回扩展字段：本接口的消费方(扩展字段面板/列表可调出列)都只认扩展字段
    return ok({
        "field_definitions": [fd for fd in schema["field_definitions"]
                              if not (isinstance(fd, dict) and fd.get("native"))],
        # 与 entity-form-schema 同口径合并系统规则，避免扩展字段条件显隐与表单不一致
        "rule_definitions": merge_system_rules(entity_type, schema["rule_definitions"]),
    })


@router.get("/entity-form-schema/{entity_type}")
async def get_entity_form_schema(
    entity_type: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """取业务表单的完整字段策略：原生字段(含租户覆盖) + 扩展字段 + 规则。

    业务表单页用它决定原生字段的必填/显隐/只读，规则条件可跨原生与扩展字段。
    """
    _check_entity(entity_type)
    return ok(await service.get_entity_form_schema(db, tenant_id, entity_type))


# ==================== 表单实例(数据) ====================

@router.get("/form-instances")
async def list_form_instances(
    template_id: str = Query(...),
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    filters: str | None = Query(None, description='JSON: {match,rules:[{field,op,value}]} 或旧版数组'),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:view")),
    scope: "list[str] | None" = Depends(get_data_scope),
):
    items, total = await service.list_instances(
        db, tenant_id, template_id, pageNo, pageSize,
        keyword=keyword, status=status, owner_ids=scope, filters=filters,
        user=user,
    )
    name_map = await service.user_display_names(
        db, tenant_id, [i.initiator_id for i in items if i.initiator_id],
    )
    return ok({
        "items": [_inst_list_dict(i, name_map) for i in items],
        "total": total, "pageNo": pageNo, "pageSize": pageSize,
    })


@router.get("/payment-registration/dashboard/summary")
async def payment_registration_dashboard_summary(
    template_id: str = Query(...),
    keyword: str = Query(None),
    status: str = Query(None),
    filters: str | None = Query(None, description='JSON: {match,rules:[{field,op,value}]}'),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:view")),
    scope: "list[str] | None" = Depends(get_data_scope),
):
    """收款登记仪表盘：来款合计等指标（筛选口径与列表一致）。"""
    data = await service.form_instance_summary(
        db, tenant_id, template_id, sum_field="payment_total",
        keyword=keyword, status=status, owner_ids=scope, filters=filters, user=user,
    )
    return ok(data)


_INST_STATUS_LABELS = {
    "draft": "草稿", "submitted": "已提交", "running": "审批中",
    "completed": "已通过", "rejected": "已驳回", "withdrawn": "已撤回",
}

# 单次导出行上限(与 service.export_instances 的 clamp 上限一致);命中即在末尾追加截断提示。
_EXPORT_ROW_CAP = 50000

_UUID_EXPORT_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _collect_ref_ids(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[str] = []
        for x in value:
            out.extend(_collect_ref_ids(x))
        return out
    if isinstance(value, dict):
        rid = value.get("id")
        return [str(rid)] if rid else []
    s = str(value).strip()
    return [s] if s else []


def _accumulate_export_ref_ids(
    field_type: str | None,
    value,
    person_ids: set[str],
    dept_ids: set[str],
    project_ids: set[str],
    contract_ids: set[str],
    customer_ids: set[str],
) -> None:
    """按字段类型把引用 id 归入对应集合。"""
    ids = _collect_ref_ids(value)
    if not ids:
        return
    ftype = field_type or ""
    if ftype in ("person", "person_multi"):
        person_ids.update(ids)
    elif ftype in ("department", "department_multi"):
        dept_ids.update(ids)
    elif ftype == "project":
        project_ids.update(ids)
    elif ftype == "contract":
        contract_ids.update(ids)
    elif ftype == "customer":
        customer_ids.update(ids)


def _scan_export_ref_ids_from_defs(
    field_defs: list,
    fd_data: dict,
    person_ids: set[str],
    dept_ids: set[str],
    project_ids: set[str],
    contract_ids: set[str],
    customer_ids: set[str],
) -> None:
    """扫描主字段及 detail_table 子列中的人员/部门等引用 id。"""
    for fd in field_defs:
        if not isinstance(fd, dict) or not fd.get("id"):
            continue
        fid = str(fd.get("id"))
        ftype = str(fd.get("type") or "")
        if ftype in ("detail_table", "sub_table_data"):
            cols = fd.get("detail_table_columns") or []
            raw = fd_data.get(fid)
            if not isinstance(raw, list):
                continue
            for row in raw:
                if not isinstance(row, dict):
                    continue
                for col in cols:
                    if not isinstance(col, dict) or not col.get("id"):
                        continue
                    _accumulate_export_ref_ids(
                        col.get("type"), row.get(col.get("id")),
                        person_ids, dept_ids, project_ids, contract_ids, customer_ids,
                    )
            continue
        _accumulate_export_ref_ids(
            ftype, fd_data.get(fid),
            person_ids, dept_ids, project_ids, contract_ids, customer_ids,
        )


async def _load_export_label_maps(
    db: AsyncSession, tenant_id: str, field_defs: list, rows: list,
) -> dict[str, dict[str, str]]:
    """批量把导出里的人员/部门等 id 解析成显示名（含明细子列）。"""
    from sqlalchemy import text as sql_text

    person_ids: set[str] = set()
    dept_ids: set[str] = set()
    project_ids: set[str] = set()
    contract_ids: set[str] = set()
    customer_ids: set[str] = set()
    for inst in rows:
        if getattr(inst, "initiator_id", None):
            person_ids.add(str(inst.initiator_id))
        fd_data = inst.form_data or {}
        if not isinstance(fd_data, dict):
            continue
        _scan_export_ref_ids_from_defs(
            field_defs, fd_data,
            person_ids, dept_ids, project_ids, contract_ids, customer_ids,
        )

    async def _map(sql: str, ids: set[str]) -> dict[str, str]:
        from sqlalchemy import bindparam
        clean = [i for i in ids if i and _UUID_EXPORT_RE.match(i)]
        if not clean:
            return {}
        stmt = sql_text(sql).bindparams(bindparam("ids", expanding=True))
        rows_db = (await db.execute(stmt, {"t": tenant_id, "ids": clean})).fetchall()
        return {str(r[0]): str(r[1] or "") for r in rows_db if r[0]}

    users = await _map(
        "SELECT id, COALESCE(NULLIF(real_name,''), username, id) FROM users "
        "WHERE tenant_id = :t AND id IN :ids",
        person_ids,
    )
    depts = await _map(
        "SELECT id, name FROM departments WHERE tenant_id = :t AND id IN :ids",
        dept_ids,
    )
    projects = await _map(
        "SELECT id, COALESCE(NULLIF(project_code,''), NULLIF(name,''), id) FROM opportunity_projects "
        "WHERE tenant_id = :t AND id IN :ids",
        project_ids,
    )
    contracts = await _map(
        "SELECT id, COALESCE(NULLIF(contract_no,''), id) FROM contracts "
        "WHERE tenant_id = :t AND id IN :ids",
        contract_ids,
    )
    customers = await _map(
        "SELECT id, COALESCE(NULLIF(name,''), id) FROM customers "
        "WHERE tenant_id = :t AND id IN :ids",
        customer_ids,
    )
    return {
        "users": users, "depts": depts, "projects": projects,
        "contracts": contracts, "customers": customers,
    }


def _export_detail_columns(detail_fd: dict, roles: set[str]) -> list[dict]:
    """明细表导出列：有 id 且对当前角色可见。"""
    from app.domains.lowcode.field_permission import field_visible

    cols = detail_fd.get("detail_table_columns") or []
    out: list[dict] = []
    for col in cols:
        if not isinstance(col, dict) or not col.get("id"):
            continue
        if not field_visible(col, roles):
            continue
        out.append(col)
    return out


def _export_detail_col_specs(
    detail_fields: list,
    roles: set[str],
) -> tuple[list[tuple[dict, dict]], list[str]]:
    """明细列定义与表头；仅当不同子表存在同名列时才加子表前缀。"""
    specs: list[tuple[dict, dict]] = []
    clabels: list[str] = []
    for dfd in detail_fields:
        for col in _export_detail_columns(dfd, roles):
            specs.append((dfd, col))
            clabels.append(str(col.get("label") or col.get("id") or ""))
    dup = {lb for lb in clabels if lb and clabels.count(lb) > 1}
    headers: list[str] = []
    for (dfd, col), clabel in zip(specs, clabels):
        if clabel in dup:
            dlabel = str(dfd.get("label") or dfd.get("id") or "明细")
            headers.append(f"{dlabel}·{clabel}")
        else:
            headers.append(clabel)
    return specs, headers


def _detail_row_count(fd_data: dict, dfd: dict) -> int:
    fid = dfd.get("id")
    raw = fd_data.get(fid) if fid else None
    if not isinstance(raw, list):
        return 0
    return sum(1 for row in raw if isinstance(row, dict))


def _build_form_export_sheets(
    *,
    sheet_title: str,
    data_fields: list,
    filtered_rows: list[tuple],
    label_maps: dict[str, dict[str, str]],
    roles: set[str],
    truncated: bool,
    layout: str = "flat",
) -> list[tuple[str, list[str], list[list]]]:
    """导出 sheet 列表。filtered_rows: [(inst, fd_data), ...]。

    layout=flat（默认）：单 sheet，主表字段与明细按行展开（每条明细一行，主字段重复）。
    layout=multi：主表 + 每个明细子表各一张 sheet（旧版简道云风格）。
    """
    users = (label_maps or {}).get("users") or {}
    meta_headers = ["业务编号", "标题", "状态", "创建人", "创建时间"]

    if layout == "flat":
        scalar_fields = [
            fd for fd in data_fields
            if (fd.get("type") or "") not in ("detail_table", "sub_table_data")
        ]
        detail_fields = [
            fd for fd in data_fields
            if (fd.get("type") or "") in ("detail_table", "sub_table_data")
        ]
        detail_col_specs, detail_headers = _export_detail_col_specs(detail_fields, roles)

        main_headers = list(meta_headers)
        main_headers += [str(fd.get("label") or fd.get("id") or "") for fd in scalar_fields]
        main_headers += detail_headers

        main_rows: list[list] = []
        for inst, fd_data in filtered_rows:
            initiator_id = getattr(inst, "initiator_id", None) or ""
            base = [
                inst.business_no or "", inst.title or "",
                _INST_STATUS_LABELS.get(inst.status, inst.status or ""),
                users.get(str(initiator_id), "") if initiator_id else "",
                inst.created_at.strftime("%Y-%m-%d %H:%M") if inst.created_at else "",
            ]
            base += [
                _fmt_export_cell(fd.get("type"), fd_data.get(fd.get("id")), label_maps)
                for fd in scalar_fields
            ]
            detail_counts = [_detail_row_count(fd_data, dfd) for dfd in detail_fields]
            row_count = max(detail_counts + [1])
            for idx in range(row_count):
                line = list(base)
                for dfd, col in detail_col_specs:
                    fid = dfd.get("id")
                    raw = fd_data.get(fid) if fid else None
                    cell = ""
                    if isinstance(raw, list) and idx < len(raw) and isinstance(raw[idx], dict):
                        cell = _fmt_export_cell(
                            col.get("type"), raw[idx].get(col.get("id")), label_maps,
                        )
                    line.append(cell)
                main_rows.append(line)
        if truncated:
            note = [
                f"⚠ 数据超过导出上限 {_EXPORT_ROW_CAP} 条，已按最新时间截断，请缩小筛选范围后再导出",
            ]
            main_rows.append(note + [""] * (len(main_headers) - 1))
        return [(sheet_title or "表单数据", main_headers, main_rows)]

    main_headers = meta_headers + [fd.get("label") or fd.get("id") for fd in data_fields]
    main_rows = []
    for inst, fd_data in filtered_rows:
        initiator_id = getattr(inst, "initiator_id", None) or ""
        line = [
            inst.business_no or "", inst.title or "",
            _INST_STATUS_LABELS.get(inst.status, inst.status or ""),
            users.get(str(initiator_id), "") if initiator_id else "",
            inst.created_at.strftime("%Y-%m-%d %H:%M") if inst.created_at else "",
        ]
        line += [
            _fmt_export_cell(fd.get("type"), fd_data.get(fd.get("id")), label_maps)
            for fd in data_fields
        ]
        main_rows.append(line)
    if truncated:
        note = [
            f"⚠ 数据超过导出上限 {_EXPORT_ROW_CAP} 条，已按最新时间截断，请缩小筛选范围后再导出",
        ]
        main_rows.append(note + [""] * (len(main_headers) - 1))

    sheets: list[tuple[str, list[str], list[list]]] = [
        (sheet_title or "表单数据", main_headers, main_rows),
    ]

    detail_fields = [
        fd for fd in data_fields
        if (fd.get("type") or "") in ("detail_table", "sub_table_data")
    ]
    for dfd in detail_fields:
        cols = _export_detail_columns(dfd, roles)
        d_headers = (
            ["业务编号", "标题", "状态"]
            + [c.get("label") or c.get("id") for c in cols]
        )
        d_rows: list[list] = []
        fid = dfd.get("id")
        for inst, fd_data in filtered_rows:
            raw = fd_data.get(fid) if fid else None
            if not isinstance(raw, list):
                continue
            base = [
                inst.business_no or "",
                inst.title or "",
                _INST_STATUS_LABELS.get(inst.status, inst.status or ""),
            ]
            for row in raw:
                if not isinstance(row, dict):
                    continue
                d_rows.append(
                    base + [
                        _fmt_export_cell(c.get("type"), row.get(c.get("id")), label_maps)
                        for c in cols
                    ]
                )
        sheets.append((str(dfd.get("label") or dfd.get("id") or "明细"), d_headers, d_rows))

    return sheets


def _fmt_export_cell(
    field_type: str | None, value, labels: dict[str, dict[str, str]] | None = None,
) -> str:
    """把表单字段值格式化成单元格文本（列表/子表/文件等做可读摘要）。"""
    if value is None or value == "":
        return ""
    if field_type in ("detail_table", "sub_table_data"):
        return f"{len(value)} 行" if isinstance(value, list) else str(value)
    if field_type in ("file", "image"):
        return f"{len(value)} 个文件" if isinstance(value, list) else str(value)
    if field_type == "switch" or isinstance(value, bool):
        return "是" if value else "否"

    labels = labels or {}
    if field_type in ("person", "person_multi"):
        m = labels.get("users") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)
    if field_type in ("department", "department_multi"):
        m = labels.get("depts") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)
    if field_type == "project":
        m = labels.get("projects") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)
    if field_type == "contract":
        m = labels.get("contracts") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)
    if field_type == "customer":
        m = labels.get("customers") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)

    if isinstance(value, list):
        return "、".join(
            str(v.get("name") or v.get("label") or v.get("id") or v) if isinstance(v, dict) else str(v)
            for v in value
        )
    if isinstance(value, dict):
        return str(value.get("name") or value.get("label") or value.get("text") or value)
    return str(value)


@router.get("/form-instances/export")
async def export_form_instances(
    template_id: str = Query(...),
    keyword: str = Query(None),
    status: str = Query(None),
    filters: str | None = Query(None, description='JSON: {match,rules:[{field,op,value}]} 或旧版数组'),
    layout: str = Query("flat", description="flat=单 sheet 主从合并行展开；multi=主表+各明细分 sheet"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:view")),
    scope: "list[str] | None" = Depends(get_data_scope),
):
    """导出当前筛选下的表单数据为 Excel（默认单 sheet，主表与明细合并按行展开）。"""
    tpl, field_defs, rows = await service.export_instances(
        db, tenant_id, template_id, keyword=keyword, status=status, owner_ids=scope,
        filters=filters, limit=_EXPORT_ROW_CAP, user=user,
    )
    # 字段级权限：导出列同样剔除对该用户隐藏的字段；附件无下载权则导出空
    from app.domains.lowcode.field_permission import field_visible, filter_read
    _roles = set(user.get("roles") or [])
    data_fields = [fd for fd in field_defs if fd.get("id") and field_visible(fd, _roles)]
    label_maps = await _load_export_label_maps(db, tenant_id, field_defs, rows)
    uid = user.get("sub")
    filtered_rows: list[tuple] = []
    for inst in rows:
        is_creator = bool(uid and (
            uid == getattr(inst, "created_by", None)
            or uid == getattr(inst, "initiator_id", None)
        ))
        _, fd_data = filter_read(
            field_defs, inst.form_data or {}, _roles, is_creator=is_creator,
        )
        filtered_rows.append((inst, fd_data))
    export_layout = "multi" if (layout or "").strip().lower() == "multi" else "flat"
    sheets = _build_form_export_sheets(
        sheet_title=(tpl.name if tpl else "表单数据"),
        data_fields=data_fields,
        filtered_rows=filtered_rows,
        label_maps=label_maps,
        roles=_roles,
        truncated=len(rows) >= _EXPORT_ROW_CAP,
        layout=export_layout,
    )
    buf = build_excel_multi(sheets)
    fname = f"{(tpl.name if tpl else '表单数据')}.xlsx"
    return excel_response(buf, fname)


@router.post("/form-instances")
async def create_form_instance(
    body: schemas.FormInstanceCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:create")),
):
    inst = await service.create_instance(db, tenant_id, body, user)
    return ok({"id": inst.id, "status": inst.status, "business_no": inst.business_no})


@router.get("/form-instances/{instance_id}")
async def get_form_instance(
    instance_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """查看表单数据。审批相关人可只读旁路（不必有 form_data:view）。"""
    perms = user.get("permissions") or []
    if "form_data:view" not in perms:
        from app.domains.lowcode import workflow_service as wsvc
        if not await wsvc.can_access_form_via_workflow(db, tenant_id, user.get("sub"), instance_id):
            raise BusinessException(code=FORBIDDEN, message="缺少权限: form_data:view")
    return ok(await service.get_instance(db, tenant_id, instance_id, user=user))


@router.put("/form-instances/{instance_id}")
async def update_form_instance(
    instance_id: str,
    body: schemas.FormInstanceUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:edit")),
):
    inst = await service.update_instance(db, tenant_id, instance_id, body, user)
    return ok({"id": inst.id, "status": inst.status})


@router.post("/form-instances/{instance_id}/submit")
async def submit_form_instance(
    instance_id: str,
    body: schemas.FormInstanceSubmit | None = None,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:edit")),
):
    """草稿提交审批（与新建时点「提交」等价）。"""
    inst = await service.submit_instance(
        db, tenant_id, instance_id, body or schemas.FormInstanceSubmit(), user,
    )
    return ok({
        "id": inst.id,
        "status": inst.status,
        "business_no": inst.business_no,
        "process_instance_id": inst.process_instance_id,
    })


@router.delete("/form-instances/{instance_id}")
async def delete_form_instance(
    instance_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:delete")),
):
    await service.delete_instance(db, tenant_id, instance_id, user)
    return ok(None)
