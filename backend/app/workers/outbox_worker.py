"""
Outbox Worker — polls outbox_events table and dispatches to webhook subscribers.

Usage:
    python -m app.workers.outbox_worker

Runs as an independent process. Polls pending events, matches webhook subscriptions,
delivers payloads with HMAC signing, and handles retries with exponential backoff.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import random
import time

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.domains.outbox.models import OutboxEvent
from app.domains.admin.models import WebhookSubscription

logger = logging.getLogger("outbox_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

MAX_RETRIES = 5
POLL_INTERVAL = 5  # seconds
BATCH_SIZE = 20
REQUEST_TIMEOUT = 15  # seconds


def compute_hmac(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def fetch_pending_events(db: AsyncSession, batch_size: int = BATCH_SIZE) -> list[OutboxEvent]:
    """Fetch pending events across all tenants, respecting backoff windows."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(OutboxEvent)
        .where(OutboxEvent.status.in_(["pending", "failed"]))
        .where(OutboxEvent.retry_count < MAX_RETRIES)
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
    )
    events = list(result.scalars().all())
    # Filter out events still in backoff window (with jitter)
    ready = []
    for e in events:
        if e.status == "pending" or e.retry_count == 0:
            ready.append(e)
        else:
            backoff = min(2 ** e.retry_count + random.uniform(0, 5), 300)
            if e.updated_at and (now - e.updated_at).total_seconds() >= backoff:
                ready.append(e)
    return ready


async def fetch_webhook_subscriptions(db: AsyncSession, tenant_id: str, event_type: str) -> list[WebhookSubscription]:
    """Find active webhook subscriptions matching the event type for a tenant."""
    result = await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.tenant_id == tenant_id,
            WebhookSubscription.status == "active",
        )
    )
    subs = result.scalars().all()
    matched = []
    for sub in subs:
        event_types = sub.event_types_json
        if not event_types:
            matched.append(sub)  # No filter = subscribe to all
            continue
        # event_types_json can be a list or dict with keys
        if isinstance(event_types, list):
            if event_type in event_types or "*" in event_types:
                matched.append(sub)
        elif isinstance(event_types, dict):
            if event_type in event_types or "*" in event_types:
                matched.append(sub)
    return matched


async def deliver_webhook(url: str, payload: dict, secret: str | None) -> tuple[bool, str]:
    """Deliver payload to a webhook URL. Returns (success, detail)."""
    body = json.dumps(payload, ensure_ascii=False, default=str)
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = compute_hmac(secret, body)
        headers["X-Webhook-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, content=body, headers=headers)
            if 200 <= resp.status_code < 300:
                return True, f"HTTP {resp.status_code}"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except httpx.TimeoutException:
        return False, "Request timed out"
    except Exception as e:
        return False, str(e)[:200]


async def process_event(db: AsyncSession, event: OutboxEvent):
    """Process a single outbox event: match subscriptions and deliver."""
    subs = await fetch_webhook_subscriptions(db, event.tenant_id, event.event_type)

    if not subs:
        # No subscribers — mark as published (nothing to do)
        event.status = "published"
        event.published_by = "outbox_worker:no_subscribers"
        await db.commit()
        logger.info(f"Event {event.id} ({event.event_type}): no subscribers, marked published")
        return

    payload = {
        "event_id": event.id,
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "tenant_id": event.tenant_id,
        "timestamp": event.created_at.isoformat() if event.created_at else "",
        "data": event.payload_json,
    }

    all_success = True
    errors = []
    for sub in subs:
        success, detail = await deliver_webhook(sub.target_url, payload, sub.secret_token)
        if success:
            logger.info(f"Event {event.id} → {sub.target_url}: {detail}")
        else:
            all_success = False
            errors.append(f"{sub.target_url}: {detail}")
            logger.warning(f"Event {event.id} → {sub.target_url} FAILED: {detail}")

    if all_success:
        event.status = "published"
        event.published_by = "outbox_worker"
    else:
        event.status = "failed"
        event.retry_count += 1
        event.error_message = "; ".join(errors)

    await db.commit()


async def process_email_events(db: AsyncSession, event: OutboxEvent):
    """Handle email-type events via email service."""
    if event.event_type != "email.send":
        return False

    try:
        from app.common.email_service import send_email
        data = event.payload_json or {}
        success = await send_email(
            db=db, tenant_id=event.tenant_id,
            to=data.get("to", ""),
            subject=data.get("subject", ""),
            body_html=data.get("body_html", ""),
        )
        if success:
            event.status = "published"
            event.published_by = "outbox_worker:email"
        else:
            logger.warning("Email send returned failure for event=%s to=%s tenant=%s",
                           event.id, data.get("to", "?"), event.tenant_id)
            event.status = "failed"
            event.retry_count += 1
            event.error_message = "Email send failed"
        await db.commit()
        return True
    except Exception as e:
        data = event.payload_json or {}
        logger.warning("Email send failed for event=%s to=%s tenant=%s: %s",
                        event.id, data.get("to", "?"), event.tenant_id, e)
        event.status = "failed"
        event.retry_count += 1
        event.error_message = str(e)[:200]
        await db.commit()
        return True


async def run_once():
    """Single poll cycle."""
    async with async_session_factory() as db:
        events = await fetch_pending_events(db)
        if not events:
            return 0

        count = 0
        for event in events:
            try:
                # Check exponential backoff for retries
                if event.retry_count > 0:
                    backoff = min(2 ** event.retry_count, 300)  # max 5 minutes
                    if event.updated_at:
                        elapsed = time.time() - event.updated_at.timestamp()
                        if elapsed < backoff:
                            continue

                # Try email handler first
                handled = await process_email_events(db, event)
                if not handled:
                    await process_event(db, event)
                count += 1
            except Exception as e:
                logger.error(f"Error processing event {event.id}: {e}")
                try:
                    event.status = "failed"
                    event.retry_count += 1
                    event.error_message = str(e)[:200]
                    await db.commit()
                except Exception:
                    await db.rollback()
        return count


async def main():
    logger.info("Outbox Worker started. Polling every %ds...", POLL_INTERVAL)
    while True:
        try:
            count = await run_once()
            if count:
                logger.info(f"Processed {count} events")
        except Exception as e:
            logger.error(f"Poll cycle error: {e}")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
