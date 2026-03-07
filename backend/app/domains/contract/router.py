from fastapi import APIRouter, Depends, Query
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
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("contract:view")),
):
    from app.domains.contract.models import Contract
    q = select(Contract).where(Contract.tenant_id == tenant_id)
    cq = select(func.count(Contract.id)).where(Contract.tenant_id == tenant_id)
    if status:
        q = q.where(Contract.status == status)
        cq = cq.where(Contract.status == status)
    total = (await db.execute(cq)).scalar() or 0
    items = (await db.execute(
        q.order_by(Contract.created_at.desc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).scalars().all()
    return ok({"items": [_contract_dict(c) for c in items], "total": total})


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
