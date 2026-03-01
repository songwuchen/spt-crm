from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.quote import service
from app.domains.quote.schemas import QuoteCreate, QuoteUpdate, QuoteVersionUpdate, QuoteLineCreate, QuoteLineUpdate, CostSnapshotCreate, QuoteSendLogCreate

router = APIRouter(tags=["报价管理"])


def _quote_dict(q) -> dict:
    return {
        "id": q.id, "project_id": q.project_id, "quote_no": q.quote_no,
        "current_version_no": q.current_version_no, "status": q.status,
        "created_by_id": q.created_by_id, "created_by_name": q.created_by_name,
        "created_at": q.created_at.isoformat() if q.created_at else "",
        "updated_at": q.updated_at.isoformat() if q.updated_at else "",
    }


def _version_dict(v) -> dict:
    return {
        "id": v.id, "quote_id": v.quote_id, "version_no": v.version_no,
        "title": v.title,
        "price_total": float(v.price_total) if v.price_total is not None else None,
        "tax_rate": float(v.tax_rate) if v.tax_rate is not None else None,
        "tax_total": float(v.tax_total) if v.tax_total is not None else None,
        "discount_total": float(v.discount_total) if v.discount_total is not None else None,
        "margin_rate": float(v.margin_rate) if v.margin_rate is not None else None,
        "delivery_promise_date": str(v.delivery_promise_date) if v.delivery_promise_date else None,
        "validity_days": v.validity_days,
        "terms_summary_json": v.terms_summary_json,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else "",
    }


def _line_dict(l) -> dict:
    return {
        "id": l.id, "quote_version_id": l.quote_version_id, "line_no": l.line_no,
        "item_type": l.item_type, "item_name": l.item_name,
        "item_code": l.item_code, "spec": l.spec,
        "qty": float(l.qty) if l.qty is not None else None,
        "unit": l.unit,
        "unit_price": float(l.unit_price) if l.unit_price is not None else None,
        "line_total": float(l.line_total) if l.line_total is not None else None,
        "cost_est": float(l.cost_est) if l.cost_est is not None else None,
        "leadtime_days": l.leadtime_days,
    }


# --- Project-scoped routes ---
@router.get("/api/v1/projects/{project_id}/quotes")
async def list_project_quotes(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("quote:view")),
):
    items = await service.list_quotes_by_project(db, tenant_id, project_id)
    return ok([_quote_dict(q) for q in items])


@router.post("/api/v1/projects/{project_id}/quotes")
async def create_quote(
    project_id: str,
    body: QuoteCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:create")),
):
    result = await service.create_quote(db, tenant_id, project_id, body, current_user)
    return ok({
        "quote": _quote_dict(result["quote"]),
        "version": _version_dict(result["version"]),
    })


# --- Quote routes ---
@router.get("/api/v1/quotes/{quote_id}")
async def get_quote(
    quote_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("quote:view")),
):
    quote = await service.get_quote(db, tenant_id, quote_id)
    versions = await service.get_versions_by_quote(db, tenant_id, quote_id)

    # Get current version lines
    current_ver = next((v for v in versions if v.version_no == quote.current_version_no), None)
    lines = []
    if current_ver:
        lines = await service.list_lines(db, tenant_id, current_ver.id)

    return ok({
        **_quote_dict(quote),
        "versions": [_version_dict(v) for v in versions],
        "current_version": _version_dict(current_ver) if current_ver else None,
        "lines": [_line_dict(l) for l in lines],
    })


@router.put("/api/v1/quotes/{quote_id}")
async def update_quote(
    quote_id: str,
    body: QuoteUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    q = await service.update_quote(db, tenant_id, quote_id, body, current_user)
    return ok(_quote_dict(q))


@router.delete("/api/v1/quotes/{quote_id}")
async def delete_quote(
    quote_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:delete")),
):
    await service.delete_quote(db, tenant_id, quote_id, current_user)
    return ok()


@router.post("/api/v1/quotes/{quote_id}/new_version")
async def new_version(
    quote_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    v = await service.new_version(db, tenant_id, quote_id, current_user)
    return ok(_version_dict(v))


# --- Version routes ---
@router.get("/api/v1/quote_versions/{version_id}")
async def get_version(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("quote:view")),
):
    version = await service.get_version(db, tenant_id, version_id)
    lines = await service.list_lines(db, tenant_id, version_id)
    return ok({**_version_dict(version), "lines": [_line_dict(l) for l in lines]})


@router.put("/api/v1/quote_versions/{version_id}")
async def update_version(
    version_id: str,
    body: QuoteVersionUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    v = await service.update_version(db, tenant_id, version_id, body, current_user)
    return ok(_version_dict(v))


@router.post("/api/v1/quote_versions/{version_id}/lines")
async def add_line(
    version_id: str,
    body: QuoteLineCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    l = await service.add_line(db, tenant_id, version_id, body, current_user)
    return ok(_line_dict(l))


@router.put("/api/v1/quote_lines/{line_id}")
async def update_line(
    line_id: str,
    body: QuoteLineUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    l = await service.update_line(db, tenant_id, line_id, body, current_user)
    return ok(_line_dict(l))


@router.delete("/api/v1/quote_lines/{line_id}")
async def delete_line(
    line_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    await service.delete_line(db, tenant_id, line_id, current_user)
    return ok()


# --- Version Comparison ---
@router.get("/api/v1/quotes/{quote_id}/compare")
async def compare_versions(
    quote_id: str,
    version_a: str = Query(...),
    version_b: str = Query(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("quote:view")),
):
    result = await service.compare_versions(db, tenant_id, version_a, version_b)
    return ok(result)


# --- Cost Snapshots ---
def _snapshot_dict(s) -> dict:
    return {
        "id": s.id, "quote_version_id": s.quote_version_id,
        "snapshot_type": s.snapshot_type,
        "price_total": float(s.price_total) if s.price_total is not None else None,
        "cost_total": float(s.cost_total) if s.cost_total is not None else None,
        "margin_rate": float(s.margin_rate) if s.margin_rate is not None else None,
        "breakdown_json": s.breakdown_json,
        "line_snapshot_json": s.line_snapshot_json,
        "note": s.note,
        "created_by_name": s.created_by_name,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


def _send_log_dict(l) -> dict:
    return {
        "id": l.id, "quote_id": l.quote_id, "quote_version_id": l.quote_version_id,
        "channel": l.channel, "to_list_json": l.to_list_json,
        "subject": l.subject, "body": l.body,
        "attachments_json": l.attachments_json,
        "status": l.status,
        "sent_by_id": l.sent_by_id, "sent_by_name": l.sent_by_name,
        "created_at": l.created_at.isoformat() if l.created_at else "",
    }


@router.get("/api/v1/quote_versions/{version_id}/cost_snapshots")
async def list_cost_snapshots(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("quote:view")),
):
    items = await service.list_cost_snapshots(db, tenant_id, version_id)
    return ok([_snapshot_dict(s) for s in items])


@router.post("/api/v1/quote_versions/{version_id}/cost_snapshots")
async def create_cost_snapshot(
    version_id: str,
    body: CostSnapshotCreate = CostSnapshotCreate(),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    s = await service.create_cost_snapshot(db, tenant_id, version_id, current_user, data=body)
    return ok(_snapshot_dict(s))


# --- Quote Send Log ---
@router.post("/api/v1/quote_versions/{version_id}/send")
async def send_quote(
    version_id: str,
    body: QuoteSendLogCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("quote:edit")),
):
    # Get quote_id from version
    version = await service.get_version(db, tenant_id, version_id)
    log = await service.create_send_log(db, tenant_id, version.quote_id, version_id, body, current_user)
    return ok(_send_log_dict(log))


@router.get("/api/v1/quotes/{quote_id}/send_logs")
async def list_send_logs(
    quote_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("quote:view")),
):
    items = await service.list_send_logs(db, tenant_id, quote_id)
    return ok([_send_log_dict(l) for l in items])
