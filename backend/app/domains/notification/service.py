import logging
from sqlalchemy import select, func, update, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.domains.notification.models import Notification, DataSubscription

logger = logging.getLogger("spt_crm.notification")


async def list_notifications(db: AsyncSession, tenant_id: str, recipient_id: str, unread_only: bool = False, limit: int = 50):
    q = select(Notification).where(
        Notification.tenant_id == tenant_id,
        Notification.recipient_id == recipient_id,
    )
    if unread_only:
        q = q.where(Notification.is_read == False)
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


async def count_unread(db: AsyncSession, tenant_id: str, recipient_id: str) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.is_read == False,
        )
    )
    return result.scalar() or 0


async def mark_read(db: AsyncSession, tenant_id: str, recipient_id: str, ids: list[str]):
    await db.execute(
        update(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.id.in_(ids),
        ).values(is_read=True)
    )
    await db.commit()


async def mark_all_read(db: AsyncSession, tenant_id: str, recipient_id: str):
    await db.execute(
        update(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.is_read == False,
        ).values(is_read=True)
    )
    await db.commit()


async def delete_notification(db: AsyncSession, tenant_id: str, recipient_id: str, notification_id: str):
    await db.execute(
        sql_delete(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.id == notification_id,
        )
    )
    await db.commit()


async def batch_delete(db: AsyncSession, tenant_id: str, recipient_id: str, ids: list[str]) -> int:
    result = await db.execute(
        sql_delete(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.id.in_(ids),
        )
    )
    await db.commit()
    return result.rowcount


async def create_notification(db: AsyncSession, tenant_id: str, data: dict) -> Notification:
    n = Notification(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


async def render_template(db: AsyncSession, tenant_id: str, event_type: str, variables: dict) -> tuple[str | None, str | None]:
    """Try to render a notification template for the given event type. Returns (title, content) or (None, None)."""
    from app.domains.notification.models import NotificationTemplate
    import re
    t = (await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.tenant_id == tenant_id,
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.is_active == True,
        ).limit(1)
    )).scalar()
    if not t:
        return None, None

    def replace_vars(text: str) -> str:
        return re.sub(r'\{\{(\w+)\}\}', lambda m: str(variables.get(m.group(1), m.group(0))), text)

    title = replace_vars(t.title_template)
    content = replace_vars(t.content_template) if t.content_template else None
    return title, content


async def send_notification(db: AsyncSession, tenant_id: str, recipient_id: str,
                            type: str, title: str, content: str | None = None,
                            biz_type: str | None = None, biz_id: str | None = None,
                            sender_name: str | None = None, extra_json: dict | None = None,
                            template_vars: dict | None = None) -> Notification:
    """Convenience function for sending a notification + real-time WS push.
    If template_vars is provided, tries to render a template first."""
    if template_vars:
        try:
            tpl_title, tpl_content = await render_template(db, tenant_id, type, template_vars)
            if tpl_title:
                title = tpl_title
            if tpl_content:
                content = tpl_content
        except Exception as e:
            logger.warning("Template rendering failed for event_type=%s: %s", type, e)

    n = await create_notification(db, tenant_id, {
        "recipient_id": recipient_id,
        "type": type,
        "title": title,
        "content": content,
        "biz_type": biz_type,
        "biz_id": biz_id,
        "sender_name": sender_name,
        "extra_json": extra_json,
    })

    # Push via WebSocket (non-blocking, non-critical)
    try:
        from app.common.ws_manager import ws_manager
        await ws_manager.send_to_user(recipient_id, {
            "event": "notification",
            "data": {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "content": n.content,
                "biz_type": n.biz_type,
                "biz_id": n.biz_id,
                "sender_name": n.sender_name,
                "is_read": False,
                "extra_json": n.extra_json,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            },
        })
    except Exception as e:
        logger.debug("WS push failed for recipient=%s: %s", recipient_id, e)

    return n


async def notify_subscribers(
    db: AsyncSession, tenant_id: str,
    biz_type: str, biz_id: str,
    event: str, title: str, content: str | None = None,
    sender_name: str | None = None, exclude_user_id: str | None = None,
):
    """Notify all users subscribed to a specific business entity about a change event."""
    subs = (await db.execute(
        select(DataSubscription).where(
            DataSubscription.tenant_id == tenant_id,
            DataSubscription.biz_type == biz_type,
            DataSubscription.biz_id == biz_id,
        )
    )).scalars().all()

    for sub in subs:
        if sub.user_id == exclude_user_id:
            continue
        events = sub.events_json or []
        if events and event not in events:
            continue
        await send_notification(
            db, tenant_id, sub.user_id,
            type="data_change",
            title=title,
            content=content,
            biz_type=biz_type,
            biz_id=biz_id,
            sender_name=sender_name,
            extra_json={"event": event},
        )
