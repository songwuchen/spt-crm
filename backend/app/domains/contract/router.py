from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.field_mask import load_mask_policies, apply_field_mask
from app.domains.contract import service
from app.domains.contract.schemas import ContractCreate, ContractUpdate, ContractVersionUpdate, ContractSign, ContractFromQuote

router = APIRouter(tags=["合同管理"])


def _contract_dict(c) -> dict:
    return {
        "id": c.id, "project_id": c.project_id, "contract_no": c.contract_no,
        "from_quote_id": c.from_quote_id,
        "current_version_no": c.current_version_no, "status": c.status,
        "signed_date": str(c.signed_date) if c.signed_date else None,
        "end_date": str(c.end_date) if c.end_date else None,
        "amount_total": float(c.amount_total) if c.amount_total is not None else None,
        "payment_terms_json": c.payment_terms_json,
        "delivery_terms_json": c.delivery_terms_json,
        "created_by_id": c.created_by_id, "created_by_name": c.created_by_name,
        "assignee_id": c.assignee_id, "assignee_name": c.assignee_name,
        "department_id": c.department_id, "department_name": c.department_name,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


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
        q = q.where(Contract.status == status)
        cq = cq.where(Contract.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(Contract.contract_no.ilike(like))
        cq = cq.where(Contract.contract_no.ilike(like))
    # 高级筛选（多字段/多条件）
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("contract", filter, {"user_id": current_user.get("sub")})
    if clause is not None:
        q = q.where(clause)
        cq = cq.where(clause)
    from app.common.data_scope import apply_project_child_scope
    q, cq = await apply_project_child_scope(q, cq, db, tenant_id, current_user, Contract)
    total = (await db.execute(cq)).scalar() or 0
    order = resolve_sort("contract", sort_by, sort_order) or Contract.created_at.desc()
    items = (await db.execute(
        q.order_by(order)
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).scalars().all()
    # 与详情保持一致的字段脱敏（避免列表泄露详情已脱敏的字段）
    perms = current_user.get("permissions", [])
    policies = await load_mask_policies(db, tenant_id)
    rows = apply_field_mask([_contract_dict(c) for c in items], "contract", perms, policies)
    return ok({"items": rows, "total": total})


# --- Project-scoped routes ---
@router.get("/api/v1/projects/{project_id}/contracts")
async def list_project_contracts(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contract:view")),
):
    items = await service.list_contracts_by_project(db, tenant_id, project_id)
    return ok([_contract_dict(c) for c in items])


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


# --- Contract routes ---
@router.get("/api/v1/contracts/{contract_id}")
async def get_contract(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:view")),
):
    contract = await service.get_contract(db, tenant_id, contract_id)
    versions = await service.get_versions_by_contract(db, tenant_id, contract_id)
    perms = current_user.get("permissions", [])
    policies = await load_mask_policies(db, tenant_id)
    contract_dict = apply_field_mask(_contract_dict(contract), "contract", perms, policies)
    return ok({
        **contract_dict,
        "versions": [_version_dict(v) for v in versions],
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
    return ok(_contract_dict(c))


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
    return ok(_contract_dict(c))


# --- Version routes ---
@router.get("/api/v1/contract_versions/{version_id}")
async def get_version(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contract:view")),
):
    v = await service.get_version(db, tenant_id, version_id)
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


# --- Renewal from Contract ---

@router.post("/api/v1/contracts/{contract_id}/renew")
async def create_renewal_from_contract(
    contract_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("contract:edit")),
):
    """Create a renewal opportunity from an expiring contract."""
    from app.domains.contract.models import Contract
    from app.domains.project.models import OpportunityProject
    from app.domains.service_ticket.models import RenewalOpportunity

    contract = (await db.execute(
        select(Contract).where(Contract.tenant_id == tenant_id, Contract.id == contract_id)
    )).scalar_one_or_none()
    if not contract:
        from app.common.exceptions import BusinessException
        raise BusinessException(message="合同不存在")

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
    contract = await service.get_contract(db, tenant_id, contract_id)
    versions = await service.get_versions_by_contract(db, tenant_id, contract_id)
    cur_ver = next((v for v in versions if v.version_no == contract.current_version_no), None)

    from app.common.pdf_builder import build_contract_pdf
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
                contract = await service.get_contract(db, tenant_id, cid)
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
