from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.outbox.models import OutboxEvent, InboxEvent
from app.domains.outbox.schemas import OutboxEventCreate, InboxEventCreate


# ==================== Outbox ====================

async def enqueue_event(db: AsyncSession, tenant_id: str, data: OutboxEventCreate) -> OutboxEvent:
    """Enqueue an outbox event (called within business transaction)."""
    event = OutboxEvent(
        id=generate_uuid(), tenant_id=tenant_id,
        event_type=data.event_type,
        aggregate_type=data.aggregate_type,
        aggregate_id=data.aggregate_id,
        payload_json=data.payload_json,
        status="pending",
    )
    db.add(event)
    # NOTE: do NOT commit here — let the caller's transaction commit both the business data and event
    return event


async def list_outbox_events(
    db: AsyncSession, tenant_id: str,
    status: str | None = None, aggregate_type: str | None = None,
    page_no: int = 1, page_size: int = 20,
):
    base = select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id)
    if status:
        base = base.where(OutboxEvent.status == status)
    if aggregate_type:
        base = base.where(OutboxEvent.aggregate_type == aggregate_type)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(OutboxEvent.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def mark_published(db: AsyncSession, tenant_id: str, event_id: str, publisher: str | None = None):
    event = (await db.execute(
        select(OutboxEvent).where(OutboxEvent.id == event_id, OutboxEvent.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not event:
        raise BusinessException(code=NOT_FOUND, message="事件不存在")
    event.status = "published"
    event.published_by = publisher
    await db.commit()
    return event


async def mark_failed(db: AsyncSession, tenant_id: str, event_id: str, error: str):
    event = (await db.execute(
        select(OutboxEvent).where(OutboxEvent.id == event_id, OutboxEvent.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not event:
        raise BusinessException(code=NOT_FOUND, message="事件不存在")
    event.status = "failed"
    event.retry_count += 1
    event.error_message = error
    await db.commit()
    return event


async def retry_event(db: AsyncSession, tenant_id: str, event_id: str):
    event = (await db.execute(
        select(OutboxEvent).where(OutboxEvent.id == event_id, OutboxEvent.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not event:
        raise BusinessException(code=NOT_FOUND, message="事件不存在")
    event.status = "pending"
    await db.commit()
    return event


# ==================== Inbox ====================

async def receive_event(db: AsyncSession, tenant_id: str, data: InboxEventCreate) -> InboxEvent:
    """Receive an external event into the inbox."""
    # Idempotency check
    if data.external_id:
        existing = (await db.execute(
            select(InboxEvent).where(
                InboxEvent.tenant_id == tenant_id,
                InboxEvent.source == data.source,
                InboxEvent.external_id == data.external_id,
            )
        )).scalar_one_or_none()
        if existing:
            return existing  # Already received

    event = InboxEvent(
        id=generate_uuid(), tenant_id=tenant_id,
        source=data.source,
        event_type=data.event_type,
        external_id=data.external_id,
        payload_json=data.payload_json,
        status="received",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_inbox_events(
    db: AsyncSession, tenant_id: str,
    status: str | None = None, source: str | None = None,
    page_no: int = 1, page_size: int = 20,
):
    base = select(InboxEvent).where(InboxEvent.tenant_id == tenant_id)
    if status:
        base = base.where(InboxEvent.status == status)
    if source:
        base = base.where(InboxEvent.source == source)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(InboxEvent.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def mark_inbox_processed(db: AsyncSession, tenant_id: str, event_id: str):
    event = (await db.execute(
        select(InboxEvent).where(InboxEvent.id == event_id, InboxEvent.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not event:
        raise BusinessException(code=NOT_FOUND, message="事件不存在")
    event.status = "processed"
    event.processed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")[:29]
    await db.commit()
    return event


async def mark_inbox_failed(db: AsyncSession, tenant_id: str, event_id: str, error: str):
    event = (await db.execute(
        select(InboxEvent).where(InboxEvent.id == event_id, InboxEvent.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not event:
        raise BusinessException(code=NOT_FOUND, message="事件不存在")
    event.status = "failed"
    event.retry_count += 1
    event.error_message = error
    await db.commit()
    return event
