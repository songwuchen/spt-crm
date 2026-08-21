from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions, get_current_user
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.common.error_codes import FORBIDDEN
from app.domains.lowcode.field_permission import ok_entity
from app.common.field_mask import load_mask_policies, apply_field_mask, masked_number
from app.domains.contract import service
from app.domains.contract.schemas import (
    ContractCreate, ContractUpdate, ContractVersionUpdate, ContractVersionSubmit,
    ContractSign, ContractFromQuote, AllocateDrawingNoRequest,
)
from app.domains.lowcode import workflow_service as wsvc


router = APIRouter(tags=["合同管理"])


async def _require_contract_view_or_wf(
    db: AsyncSession,
    tenant_id: str,
    current_user: dict,
    *,
    contract_id: str | None = None,
    version_id: str | None = None,
) -> bool:
    """返回是否走审批只读旁路（跳过数据范围）。

    - 审批相关人（待办/已办/发起/抄送/代理）：可只读，即使没有 contract:view，也不受部门数据范围限制
    - 仅有 contract:view 的普通人：仍走正常数据范围
    """
    ok_wf = await wsvc.can_access_contract_via_workflow(
        db, tenant_id, current_user.get("sub"),
        contract_id=contract_id, version_id=version_id,
    )
    if ok_wf:
        return True
    perms = current_user.get("permissions") or []
    if "contract:view" in perms:
        return False
    raise BusinessException(code=FORBIDDEN, message="缺少权限: contract:view")


def _contract_dict(c) -> dict:
    return {
        "id": c.id, "project_id": c.project_id, "customer_id": c.customer_id,
        "contract_no": c.contract_no,
        "from_quote_id": c.from_quote_id,
        "current_version_no": c.current_version_no, "status": c.status,
        "signed_date": str(c.signed_date) if c.signed_date else None,
        "end_date": str(c.end_date) if c.end_date else None,
        "drawing_no": c.drawing_no,
        "peer_contract_no": c.peer_contract_no,
        "acquire_method": c.acquire_method,
        "delivery_date": str(c.delivery_date) if c.delivery_date else None,
        "change_type": c.change_type,
        "order_date": str(c.order_date) if getattr(c, "order_date", None) else None,
        "card_date": str(c.card_date) if getattr(c, "card_date", None) else None,
        "amount_total": float(c.amount_total) if c.amount_total is not None else None,
        "payment_terms_json": c.payment_terms_json,
        "delivery_terms_json": c.delivery_terms_json,
        "registration_json": getattr(c, "registration_json", None) or {},
        "created_by_id": c.created_by_id, "created_by_name": c.created_by_name,
        "assignee_id": c.assignee_id, "assignee_name": c.assignee_name,
        "department_id": c.department_id, "department_name": c.department_name,
        # 扩展字段：contracts 表一直有这一列、管理页也能为「合同」设计字段，但出参此前
        # 从不返回、写入也不落库，功能整条链路是断的。
        "custom_fields_json": c.custom_fields_json or {},
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


async def _attach_current_version_status(db: AsyncSession, tenant_id: str, contracts, rows: list[dict]) -> list[dict]:
    """列表展示用：主表签署前一直是 draft，审批态在当前版本上。"""
    if not contracts or not rows:
        return rows
    from app.domains.contract.models import ContractVersion
    ids = [c.id for c in contracts]
    ver_rows = (await db.execute(
        select(ContractVersion.contract_id, ContractVersion.version_no, ContractVersion.status).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id.in_(ids),
        )
    )).all()
    ver_map = {(cid, vno): st for cid, vno, st in ver_rows}
    by_id = {c.id: c for c in contracts}
    for d in rows:
        c = by_id.get(d.get("id"))
        if not c:
            continue
        d["current_version_status"] = ver_map.get((c.id, c.current_version_no)) or "draft"
    return rows


def _apply_contract_display_status_filter(q, cq, tenant_id: str, status: str):
    """筛选「展示态」：draft/approving/pending_sign/rejected 看版本；signed/terminated 看主表。"""
    from app.domains.contract.models import Contract, ContractVersion
    from sqlalchemy import and_, exists

    if status in ("signed", "terminated"):
        return q.where(Contract.status == status), cq.where(Contract.status == status)

    ver_pred = {
        "draft": ContractVersion.status == "draft",
        "approving": ContractVersion.status == "submitted",
        "pending_sign": ContractVersion.status.in_(("approved", "signed")),
        "rejected": ContractVersion.status == "rejected",
    }.get(status)
    if ver_pred is None:
        # 兼容旧筛选项：直接按主表 status
        return q.where(Contract.status == status), cq.where(Contract.status == status)

    ver_exists = exists().where(and_(
        ContractVersion.tenant_id == tenant_id,
        ContractVersion.contract_id == Contract.id,
        ContractVersion.version_no == Contract.current_version_no,
        ver_pred,
    ))
    return (
        q.where(Contract.status == "draft").where(ver_exists),
        cq.where(Contract.status == "draft").where(ver_exists),
    )


def _version_dict(v) -> dict:
    return {
        "id": v.id, "contract_id": v.contract_id, "version_no": v.version_no,
        "title": v.title, "doc_attachment_id": v.doc_attachment_id,
        "key_clauses_json": v.key_clauses_json,
        "risk_level": v.risk_level, "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else "",
    }


# --- List all contracts ---
@router.get("/api/v1/contracts")
async def list_contracts(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    keyword: str = Query(None),
    filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str = Query(None),
    sort_order: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:view")),
):
    from app.domains.contract.models import Contract
    q = select(Contract).where(Contract.tenant_id == tenant_id)
    cq = select(func.count(Contract.id)).where(Contract.tenant_id == tenant_id)
    if status:
        q, cq = _apply_contract_display_status_filter(q, cq, tenant_id, status)
    if keyword:
        like = f"%{keyword}%"
        from sqlalchemy import or_
        kw_clause = or_(
            Contract.contract_no.ilike(like),
            Contract.drawing_no.ilike(like),
            Contract.peer_contract_no.ilike(like),
        )
        q = q.where(kw_clause)
        cq = cq.where(kw_clause)
    # 高级筛选（多字段/多条件，含自定义扩展字段）
    from app.common.search import (
        entity_search_context, filter_clause_from_schema_or_400, resolve_sort_from_schema,
    )
    search_schema = await entity_search_context("contract", db, tenant_id)
    clause = filter_clause_from_schema_or_400(search_schema, filter, {"user_id": current_user.get("sub")})
    if clause is not None:
        q = q.where(clause)
        cq = cq.where(clause)
    from app.common.data_scope import apply_project_child_scope
    q, cq = await apply_project_child_scope(q, cq, db, tenant_id, current_user, Contract, biz_type="contract")
    total = (await db.execute(cq)).scalar() or 0
    order = resolve_sort_from_schema(search_schema, sort_by, sort_order, Contract.created_at.desc())
    items = (await db.execute(
        q.order_by(order)
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).scalars().all()
    # 与详情保持一致的字段脱敏（避免列表泄露详情已脱敏的字段）
    perms = current_user.get("permissions", [])
    policies = await load_mask_policies(db, tenant_id)
    from app.common.list_enrich import project_names_map, customer_names_map
    name_map = await project_names_map(db, tenant_id, [c.project_id for c in items])
    # 外部合同直接挂 customer_id，需补客户名
    direct_cust = await customer_names_map(
        db, tenant_id,
        [c.customer_id for c in items if c.customer_id and not (name_map.get(c.project_id) or {}).get("customer_name")],
    )
    rows = []
    for c in items:
        base = {**_contract_dict(c), **(name_map.get(c.project_id) or {})}
        if not base.get("customer_name") and c.customer_id:
            base["customer_name"] = direct_cust.get(c.customer_id)
        rows.append(base)
    rows = await _attach_current_version_status(db, tenant_id, items, rows)
    rows = apply_field_mask(rows, "contract", perms, policies)
    # 角色键控的字段权限（隐藏/脱敏），与按权限脱敏的 apply_field_mask 并行生效
    from app.domains.lowcode.field_permission import ok_entity, strip_entity_dicts
    await strip_entity_dicts(db, tenant_id, "contract", rows, current_user.get("roles"))
    return ok({"items": rows, "total": total})


# --- Project-scoped routes ---
@router.get("/api/v1/projects/{project_id}/contracts")
async def list_project_contracts(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contract:view")),
):
    items = await service.list_contracts_by_project(db, tenant_id, project_id, _user)
    rows = [_contract_dict(c) for c in items]
    rows = await _attach_current_version_status(db, tenant_id, items, rows)
    return ok(rows)


@router.post("/api/v1/projects/{project_id}/contracts")
async def create_contract(
    project_id: str,
    body: ContractCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:create")),
):
    result = await service.create_contract(db, tenant_id, project_id, body, current_user)
    return ok({
        "contract": _contract_dict(result["contract"]),
        "version": _version_dict(result["version"]),
    })


@router.get("/api/v1/contracts/peek-drawing-no")
async def peek_drawing_no(
    order_date: str | None = Query(
        None,
        description="已废弃：图纸编号不再使用订货日；保留参数仅为兼容旧前端",
        deprecated=True,
    ),
    number_attr: str | None = Query(None, description="编号属性 WMGF|SY，默认 WMGF"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:create")),
):
    """新建合同登记时预览下一可用图纸编号（跳过合同登记/图纸对应表已占用；必要时推进计数空洞）。

    编号中的年月/年段按取号当天计算，与订货日无关。
    """
    drawing_no = await service.peek_create_drawing_no(
        db, tenant_id, current_user,
        apply_date=None,  # 取号当天；忽略 order_date
        number_attr=number_attr,
    )
    await db.commit()
    return ok({
        "drawing_no": drawing_no,
        "number_attr": service.normalize_number_attr(number_attr),
    })


@router.post("/api/v1/contracts/allocate-drawing-no")
async def allocate_drawing_no(
    body: AllocateDrawingNoRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:create")),
):
    """新建合同登记重新取号：当前号仍可用则保留，否则占号避开已占用。

    编号中的年月/年段按取号当天计算，与订货日无关。
    """
    drawing_no = await service.allocate_create_drawing_no(
        db, tenant_id, current_user,
        current=body.drawing_no,
        apply_date=None,  # 取号当天；忽略 body.order_date
        number_attr=body.number_attr,
    )
    await db.commit()
    return ok({
        "drawing_no": drawing_no,
        "number_attr": service.normalize_number_attr(body.number_attr),
    })


@router.get("/api/v1/contracts/drawing-map-lookups")
async def drawing_map_lookups(
    keyword: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """编号查询（合同评审等）：从合同图纸对应表选数。"""
    perms = set(current_user.get("permissions") or [])
    if not ({"contract:create", "contract:edit", "contract:view"} & perms):
        raise BusinessException(code=FORBIDDEN, message="缺少权限: contract:create")
    items = await service.list_drawing_map_lookups(
        db, tenant_id, current_user, keyword=keyword, limit=limit,
    )
    return ok(items)


@router.get("/api/v1/contracts/base-lookups")
async def base_form_lookups(
    type: str = Query(..., description="application_field | application_material | material_name"),
    keyword: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """基础资料选项：应用领域 / 应用物料 / 物料名称。"""
    items = await service.list_base_form_lookups(
        db, tenant_id, current_user, form_code=type, keyword=keyword, limit=limit,
    )
    return ok(items)


@router.post("/api/v1/contracts/from_quote")
async def create_from_quote(
    body: ContractFromQuote,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:create")),
):
    result = await service.create_from_quote(db, tenant_id, body.quote_id, current_user)
    return ok({
        "contract": _contract_dict(result["contract"]),
        "version": _version_dict(result["version"]),
    })


@router.post("/api/v1/contracts")
async def create_contract_standalone(
    body: ContractCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:create")),
):
    """合同管理入口创建：关联商机可选（body.project_id）。"""
    result = await service.create_contract(
        db, tenant_id, body.project_id, body, current_user,
    )
    return ok({
        "contract": _contract_dict(result["contract"]),
        "version": _version_dict(result["version"]),
    })


# --- Contract routes ---
@router.get("/api/v1/contracts/{contract_id}")
async def get_contract(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # 审批相关人可只读查看被审合同（不必具备 contract:view / 不受数据范围限制）
    via_wf = await _require_contract_view_or_wf(
        db, tenant_id, current_user, contract_id=contract_id,
    )
    contract = await service.get_contract(
        db, tenant_id, contract_id, None if via_wf else current_user,
    )
    versions = await service.get_versions_by_contract(db, tenant_id, contract_id)
    perms = current_user.get("permissions", [])
    policies = await load_mask_policies(db, tenant_id)
    contract_dict = apply_field_mask(_contract_dict(contract), "contract", perms, policies)
    # 详情也补客户名（无商机链或仅挂 customer_id 的合同）
    if contract.customer_id and not contract_dict.get("customer_name"):
        from app.common.list_enrich import customer_names_map
        names = await customer_names_map(db, tenant_id, [contract.customer_id])
        contract_dict["customer_name"] = names.get(contract.customer_id)
    from app.domains.lowcode.field_permission import strip_entity_dicts
    await strip_entity_dicts(db, tenant_id, "contract", [contract_dict], current_user.get("roles"))
    return ok({
        **contract_dict,
        "versions": [_version_dict(v) for v in versions],
    })


@router.get("/api/v1/contracts/{contract_id}/related")
async def get_contract_related(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:view")),
):
    """合同详情联动：回款计划、回款记录、发票、交付里程碑。"""
    contract = await service.get_contract(db, tenant_id, contract_id, current_user)
    from app.domains.payment.models import PaymentPlan, PaymentRecord, Invoice
    from app.domains.delivery.models import DeliveryMilestone

    plans = (await db.execute(
        select(PaymentPlan).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.source_contract_id == contract_id,
        ).order_by(PaymentPlan.due_date.asc().nullslast())
    )).scalars().all()

    records, invoices, milestones = [], [], []
    invoice_applications: list = []
    if contract.project_id:
        plan_ids = [p.id for p in plans]
        # 商机下回款：优先匹配本合同计划，否则展示商机全部回款供对照
        rq = select(PaymentRecord).where(
            PaymentRecord.tenant_id == tenant_id,
            PaymentRecord.project_id == contract.project_id,
        )
        if plan_ids:
            from sqlalchemy import or_
            rq = rq.where(or_(
                PaymentRecord.matched_plan_id.in_(plan_ids),
                PaymentRecord.matched_plan_id.is_(None),
            ))
        records = (await db.execute(rq.order_by(PaymentRecord.received_date.desc().nullslast()).limit(100))).scalars().all()
        invoices = (await db.execute(
            select(Invoice).where(
                Invoice.tenant_id == tenant_id,
                Invoice.project_id == contract.project_id,
            ).order_by(Invoice.invoice_date.desc().nullslast()).limit(50)
        )).scalars().all()
        milestones = (await db.execute(
            select(DeliveryMilestone).where(
                DeliveryMilestone.tenant_id == tenant_id,
                DeliveryMilestone.project_id == contract.project_id,
            ).order_by(DeliveryMilestone.sort_order)
        )).scalars().all()

    from app.domains.lowcode.invoice_application_fields import (
        list_invoice_applications_for_contract,
    )
    invoice_applications = await list_invoice_applications_for_contract(
        db, tenant_id,
        contract_id=contract_id,
        contract_no=contract.contract_no,
        drawing_no=contract.drawing_no,
        peer_contract_no=contract.peer_contract_no,
    )

    def _plan(p):
        return {
            "id": p.id, "plan_no": p.plan_no,
            "due_date": str(p.due_date) if p.due_date else None,
            "amount": float(p.amount) if p.amount is not None else None,
            "status": p.status, "remark": p.remark,
            "trigger_milestone_code": p.trigger_milestone_code,
        }

    def _rec(r):
        return {
            "id": r.id,
            "received_date": str(r.received_date) if r.received_date else None,
            "amount": float(r.amount) if r.amount is not None else None,
            "channel": r.channel, "reference_no": r.reference_no,
            "matched_plan_id": r.matched_plan_id, "remark": r.remark,
        }

    def _inv(i):
        return {
            "id": i.id, "invoice_no": i.invoice_no,
            "amount": float(i.amount) if i.amount is not None else None,
            "invoice_date": str(i.invoice_date) if i.invoice_date else None,
            "status": i.status, "remark": i.remark,
        }

    def _ms(m):
        return {
            "id": m.id, "milestone_code": m.milestone_code, "name": m.name,
            "plan_date": str(m.plan_date) if m.plan_date else None,
            "actual_date": str(m.actual_date) if m.actual_date else None,
            "status": m.status,
        }

    return ok({
        "payment_plans": [_plan(p) for p in plans],
        "payment_records": [_rec(r) for r in records],
        "invoices": [_inv(i) for i in invoices],
        "invoice_applications": invoice_applications,
        "milestones": [_ms(m) for m in milestones],
    })


@router.put("/api/v1/contracts/{contract_id}")
async def update_contract(
    contract_id: str,
    body: ContractUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:edit")),
):
    c = await service.update_contract(db, tenant_id, contract_id, body, current_user)
    return await ok_entity(db, tenant_id, "contract", _contract_dict(c), current_user.get("roles"))


@router.delete("/api/v1/contracts/{contract_id}")
async def delete_contract(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:delete")),
):
    await service.delete_contract(db, tenant_id, contract_id, current_user)
    return ok()


@router.post("/api/v1/contracts/{contract_id}/new_version")
async def new_version(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:edit")),
):
    v = await service.new_version(db, tenant_id, contract_id, current_user)
    return ok(_version_dict(v))


@router.post("/api/v1/contracts/{contract_id}/sign")
async def sign_contract(
    contract_id: str,
    body: ContractSign,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:sign")),
):
    c = await service.sign_contract(db, tenant_id, contract_id, body.signed_date, current_user)
    return await ok_entity(db, tenant_id, "contract", _contract_dict(c), current_user.get("roles"))


# --- Version routes ---
@router.get("/api/v1/contract_versions/{version_id}")
async def get_version(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    via_wf = await _require_contract_view_or_wf(
        db, tenant_id, current_user, version_id=version_id,
    )
    # 审批旁路：不做数据范围校验（get_version 内部若传 user 会校验）
    v = await service.get_version(db, tenant_id, version_id, None if via_wf else current_user)
    return ok(_version_dict(v))


@router.put("/api/v1/contract_versions/{version_id}")
async def update_version(
    version_id: str,
    body: ContractVersionUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:edit")),
):
    v = await service.update_version(db, tenant_id, version_id, body, current_user)
    return ok(_version_dict(v))


@router.post("/api/v1/contract_versions/{version_id}/submit")
async def submit_version(
    version_id: str,
    body: ContractVersionSubmit = ContractVersionSubmit(),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:edit")),
):
    """提交合同版本审批（优先流程管理 contract_version）。"""
    v = await service.submit_version_for_approval(
        db, tenant_id, version_id, current_user,
        assignee_ids=body.assignee_ids or None,
        assignee_names=body.assignee_names,
    )
    return ok(_version_dict(v))


# --- Renewal from Contract ---

@router.post("/api/v1/contracts/{contract_id}/renew")
async def create_renewal_from_contract(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:edit")),
):
    """Create a renewal opportunity from an expiring contract."""
    from app.domains.project.models import OpportunityProject
    from app.domains.service_ticket.models import RenewalOpportunity

    # 走 service 取，才能同时做数据范围校验（原先按 id 直查，看不见的合同也能发起续约）
    contract = await service.get_contract(db, tenant_id, contract_id, current_user)

    # Get project info for customer_id
    project = (await db.execute(
        select(OpportunityProject).where(OpportunityProject.id == contract.project_id, OpportunityProject.tenant_id == tenant_id)
    )).scalar_one_or_none()

    customer_id = project.customer_id if project else None

    renewal = RenewalOpportunity(
        tenant_id=tenant_id,
        customer_id=customer_id or "",
        name=f"续约 - {contract.contract_no}",
        amount_expect=float(contract.amount_total) if contract.amount_total else None,
        status="open",
        owner_id=current_user["sub"],
        owner_name=current_user.get("real_name") or current_user.get("username"),
        related_asset_json={"source_contract_id": contract.id, "contract_no": contract.contract_no},
        remark=f"从合同 {contract.contract_no} 发起续约",
    )
    db.add(renewal)
    await db.commit()
    await db.refresh(renewal)

    return ok({
        "id": renewal.id,
        "name": renewal.name,
        "customer_id": renewal.customer_id,
        "amount_expect": float(renewal.amount_expect) if renewal.amount_expect else None,
    })


# --- PDF Export ---
@router.get("/api/v1/contracts/{contract_id}/export/pdf")
async def export_contract_pdf(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contract:view")),
):
    contract = await service.get_contract(db, tenant_id, contract_id, _user)
    versions = await service.get_versions_by_contract(db, tenant_id, contract_id)
    cur_ver = next((v for v in versions if v.version_no == contract.current_version_no), None)

    # 导出与页面同口径脱敏：否则页面显示 *** 的金额可经 PDF 拿到真值。
    # 两套并行 —— apply_field_mask 按权限、strip_entity_dicts 按角色。
    # 必须**透传脱敏后的值**，不能只判断哨兵再回头读 contract.amount_total ——
    # mask_type 还有 null / zero 两种，那样写 zero 类型仍会打印真值。
    from app.domains.lowcode.field_permission import strip_entity_dicts
    masked = apply_field_mask(
        _contract_dict(contract), "contract",
        _user.get("permissions", []), await load_mask_policies(db, tenant_id),
    )
    await strip_entity_dicts(db, tenant_id, "contract", [masked], _user.get("roles"))

    from app.common.pdf_builder import build_contract_pdf
    pdf_bytes = build_contract_pdf(
        contract_no=contract.contract_no,
        status=contract.status,
        amount_total=masked_number(masked.get("amount_total")),
        signed_date=str(contract.signed_date) if contract.signed_date else None,
        end_date=str(contract.end_date) if contract.end_date else None,
        payment_terms=contract.payment_terms_json,
        delivery_terms=contract.delivery_terms_json,
        created_by_name=contract.created_by_name or "",
        created_at=contract.created_at.isoformat() if contract.created_at else "",
        version_no=cur_ver.version_no if cur_ver else None,
        version_title=cur_ver.title if cur_ver else None,
        key_clauses=cur_ver.key_clauses_json if cur_ver else None,
    )
    filename = f"contract_{contract.contract_no}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/v1/contracts/batch_export/pdf")
async def batch_export_contract_pdf(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contract:view")),
):
    """Batch export multiple contracts as a ZIP of PDFs."""
    import io
    import zipfile
    from app.common.pdf_builder import build_contract_pdf

    ids = body.get("ids", [])
    if not ids:
        from app.common.exceptions import BusinessException
        raise BusinessException(message="请选择要导出的合同")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in ids[:50]:
            try:
                # 越权的 id 会抛 403，被下面的 except 跳过（批量导出静默略过不可见项）
                contract = await service.get_contract(db, tenant_id, cid, _user)
                versions = await service.get_versions_by_contract(db, tenant_id, cid)
                cur_ver = next((v for v in versions if v.version_no == contract.current_version_no), None)
                pdf_bytes = build_contract_pdf(
                    contract_no=contract.contract_no,
                    status=contract.status,
                    amount_total=float(contract.amount_total) if contract.amount_total is not None else None,
                    signed_date=str(contract.signed_date) if contract.signed_date else None,
                    end_date=str(contract.end_date) if contract.end_date else None,
                    payment_terms=contract.payment_terms_json,
                    delivery_terms=contract.delivery_terms_json,
                    created_by_name=contract.created_by_name or "",
                    created_at=contract.created_at.isoformat() if contract.created_at else "",
                    version_no=cur_ver.version_no if cur_ver else None,
                    version_title=cur_ver.title if cur_ver else None,
                    key_clauses=cur_ver.key_clauses_json if cur_ver else None,
                )
                zf.writestr(f"contract_{contract.contract_no}.pdf", pdf_bytes)
            except Exception:
                continue

    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="contracts_export.zip"'},
    )
