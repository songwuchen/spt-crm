from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.outbox import service
from app.domains.outbox.schemas import OutboxEventCreate, InboxEventCreate

router = APIRouter(prefix="/api/v1/events", tags=["事件总线"])


def _outbox_dict(e) -> dict:
    return {
        "id": e.id, "event_type": e.event_type,
        "aggregate_type": e.aggregate_type, "aggregate_id": e.aggregate_id,
        "payload_json": e.payload_json, "status": e.status,
        "retry_count": e.retry_count, "error_message": e.error_message,
        "published_by": e.published_by,
        "created_at": e.created_at.isoformat() if e.created_at else "",
    }


def _inbox_dict(e) -> dict:
    return {
        "id": e.id, "source": e.source, "event_type": e.event_type,
        "external_id": e.external_id,
        "payload_json": e.payload_json, "status": e.status,
        "retry_count": e.retry_count, "error_message": e.error_message,
        "processed_at": e.processed_at,
        "created_at": e.created_at.isoformat() if e.created_at else "",
    }


# ---- Outbox ----
@router.get("/outbox")
async def list_outbox(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    aggregate_type: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items, total = await service.list_outbox_events(db, tenant_id, status, aggregate_type, pageNo, pageSize)
    return ok({"items": [_outbox_dict(e) for e in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/outbox")
async def create_outbox_event(
    body: OutboxEventCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    e = await service.enqueue_event(db, tenant_id, body)
    await db.commit()
    await db.refresh(e)
    return ok(_outbox_dict(e))


@router.post("/outbox/{event_id}/publish")
async def publish_event(
    event_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    e = await service.mark_published(db, tenant_id, event_id, current_user.get("username"))
    return ok(_outbox_dict(e))


@router.post("/outbox/{event_id}/retry")
async def retry_outbox_event(
    event_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:edit")),
):
    e = await service.retry_event(db, tenant_id, event_id)
    return ok(_outbox_dict(e))


# ---- Inbox ----
@router.get("/inbox")
async def list_inbox(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    source: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items, total = await service.list_inbox_events(db, tenant_id, status, source, pageNo, pageSize)
    return ok({"items": [_inbox_dict(e) for e in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/inbox")
async def receive_inbox_event(
    body: InboxEventCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    e = await service.receive_event(db, tenant_id, body)
    return ok(_inbox_dict(e))


@router.post("/webhook/test")
async def test_webhook(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    """Send a test payload to a webhook URL and return the response."""
    import httpx
    url = body.get("url", "")
    if not url:
        from app.common.exceptions import BusinessException
        raise BusinessException(message="请提供 webhook URL")
    test_payload = {
        "event": "test",
        "tenant_id": tenant_id,
        "message": "This is a test webhook from SPT-CRM",
        "triggered_by": current_user.get("real_name") or current_user.get("username"),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=test_payload)
            return ok({
                "status_code": resp.status_code,
                "response_body": resp.text[:500],
                "success": 200 <= resp.status_code < 300,
            })
    except httpx.TimeoutException:
        return ok({"status_code": 0, "response_body": "请求超时", "success": False})
    except Exception as e:
        return ok({"status_code": 0, "response_body": str(e)[:200], "success": False})


@router.post("/inbox/{event_id}/process")
async def mark_processed(
    event_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:edit")),
):
    e = await service.mark_inbox_processed(db, tenant_id, event_id)
    return ok(_inbox_dict(e))
