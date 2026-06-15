"""Internal admin endpoints for the Open API platform — `/api/admin/v1/tenant/openapi/*`.

Guarded by the internal JWT + ``role:manage`` (same permission the existing
webhook / integration admin already uses). Webhook subscriptions continue to be
managed by the existing `/api/admin/v1/tenant/webhooks` endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.openapi import service
from app.domains.openapi.schemas import OpenApiAppCreate, OpenApiAppUpdate, ALL_SCOPES
from app.domains.outbox import service as outbox_service

router = APIRouter(prefix="/api/admin/v1/tenant/openapi", tags=["管理后台"])

_guard = require_permissions("role:manage")


@router.get("/scopes")
async def list_scopes(_user=Depends(_guard)):
    """Catalogue of grantable scopes (for the management UI)."""
    return ok(ALL_SCOPES)


@router.get("/apps")
async def list_apps(
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    apps = await service.list_apps(db, tenant_id)
    return ok([service.app_to_dict(a) for a in apps])


@router.post("/apps")
async def create_app(
    body: OpenApiAppCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    app, secret = await service.create_app(db, tenant_id, body)
    # secret is returned exactly once — the client must store it now.
    return ok({**service.app_to_dict(app), "secret": secret})


@router.put("/apps/{app_id}")
async def update_app(
    app_id: str, body: OpenApiAppUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    app = await service.update_app(db, tenant_id, app_id, body)
    return ok(service.app_to_dict(app))


@router.post("/apps/{app_id}/regenerate-secret")
async def regenerate_secret(
    app_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    app, secret = await service.regenerate_secret(db, tenant_id, app_id)
    return ok({**service.app_to_dict(app), "secret": secret})


@router.delete("/apps/{app_id}")
async def delete_app(
    app_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    await service.delete_app(db, tenant_id, app_id)
    return ok(None)


@router.get("/call-logs")
async def list_call_logs(
    app_key: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    rows, total = await service.list_call_logs(
        db, tenant_id, app_key=app_key, page=page, page_size=page_size,
    )
    items = [{
        "id": r.id, "trace_id": r.trace_id, "app_key": r.app_key,
        "method": r.method, "path": r.path, "query_string": r.query_string,
        "status_code": r.status_code, "error_code": r.error_code,
        "duration_ms": r.duration_ms, "client_ip": r.client_ip,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
    return ok({"items": items, "total": total, "pageNo": page, "pageSize": page_size})


# ---------------------------------------------------- webhook test / redeliver
@router.post("/webhooks/{subscription_id}/test")
async def test_webhook(
    subscription_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    """Send a signed sample event to the subscription's callback URL."""
    result = await service.send_test_webhook(db, tenant_id, subscription_id)
    return ok(result)


@router.get("/events")
async def list_events(
    status: str | None = Query(None, description="pending / published / failed"),
    aggregate_type: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    items, total = await outbox_service.list_outbox_events(
        db, tenant_id, status=status, aggregate_type=aggregate_type,
        page_no=page, page_size=page_size,
    )
    rows = [{
        "id": e.id, "event_type": e.event_type, "aggregate_type": e.aggregate_type,
        "aggregate_id": e.aggregate_id, "status": e.status, "retry_count": e.retry_count,
        "error_message": e.error_message, "published_by": e.published_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in items]
    return ok({"items": rows, "total": total, "pageNo": page, "pageSize": page_size})


@router.post("/events/{event_id}/redeliver")
async def redeliver_event(
    event_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(_guard),
):
    """Re-queue a failed/published event so the outbox worker delivers it again."""
    e = await outbox_service.retry_event(db, tenant_id, event_id)
    return ok({"id": e.id, "status": e.status})
