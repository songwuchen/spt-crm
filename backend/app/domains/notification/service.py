from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.domains.notification.models import Notification


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


async def create_notification(db: AsyncSession, tenant_id: str, data: dict) -> Notification:
    n = Notification(id=generate_uuid(), tenant_id=tenant_id, **data)
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


async def send_notification(db: AsyncSession, tenant_id: str, recipient_id: str,
                            type: str, title: str, content: str | None = None,
                            biz_type: str | None = None, biz_id: str | None = None,
                            sender_name: str | None = None, extra_json: dict | None = None) -> Notification:
    """Convenience function for sending a notification + real-time WS push."""
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
    except Exception:
        pass

    return n
