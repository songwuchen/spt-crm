import logging
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.notification import service
from app.domains.notification.schemas import MarkReadRequest
from app.common.ws_manager import ws_manager

logger = logging.getLogger("spt_crm.ws")

router = APIRouter(tags=["通知中心"])


def _notif_dict(n) -> dict:
    return {
        "id": n.id, "type": n.type, "title": n.title, "content": n.content,
        "biz_type": n.biz_type, "biz_id": n.biz_id,
        "sender_name": n.sender_name, "is_read": n.is_read,
        "extra_json": n.extra_json,
        "created_at": n.created_at.isoformat() if n.created_at else "",
    }


@router.get("/api/v1/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    items = await service.list_notifications(db, tenant_id, current_user["sub"], unread_only)
    return ok([_notif_dict(n) for n in items])


@router.get("/api/v1/notifications/unread_count")
async def unread_count(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    count = await service.count_unread(db, tenant_id, current_user["sub"])
    return ok({"count": count})


@router.post("/api/v1/notifications/mark_read")
async def mark_read(
    body: MarkReadRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    await service.mark_read(db, tenant_id, current_user["sub"], body.ids)
    return ok(None)


@router.post("/api/v1/notifications/mark_all_read")
async def mark_all_read(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    await service.mark_all_read(db, tenant_id, current_user["sub"])
    return ok(None)


@router.delete("/api/v1/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    await service.delete_notification(db, tenant_id, current_user["sub"], notification_id)
    return ok(None)


@router.post("/api/v1/notifications/batch_delete")
async def batch_delete(
    body: MarkReadRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    count = await service.batch_delete(db, tenant_id, current_user["sub"], body.ids)
    return ok({"deleted": count})


# ---- Notification Preferences ----

NOTIFICATION_TYPES = [
    {"key": "approval_pending", "label": "待审批通知"},
    {"key": "approval_decided", "label": "审批结果通知"},
    {"key": "stage_change", "label": "阶段变更通知"},
    {"key": "payment_overdue", "label": "回款逾期提醒"},
    {"key": "ai_task_complete", "label": "AI任务完成"},
    {"key": "gate_blocked", "label": "关卡阻断提醒"},
    {"key": "contract_expiry", "label": "合同到期提醒"},
    {"key": "system", "label": "系统通知"},
]


@router.get("/api/v1/notifications/preferences")
async def get_preferences(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    from sqlalchemy import select
    from app.domains.notification.models import NotificationPreference
    pref = (await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.user_id == current_user["sub"],
        )
    )).scalar()
    prefs = pref.preferences_json if pref else {}
    return ok({"types": NOTIFICATION_TYPES, "preferences": prefs})


@router.put("/api/v1/notifications/preferences")
async def update_preferences(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    from sqlalchemy import select
    from app.domains.notification.models import NotificationPreference
    pref = (await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.user_id == current_user["sub"],
        )
    )).scalar()
    prefs = body.get("preferences", {})
    if pref:
        pref.preferences_json = prefs
    else:
        pref = NotificationPreference(
            tenant_id=tenant_id, user_id=current_user["sub"],
            preferences_json=prefs,
        )
        db.add(pref)
    await db.commit()
    return ok({"preferences": prefs})


@router.websocket("/ws/notifications")
async def ws_notifications(ws: WebSocket):
    """WebSocket endpoint for real-time notifications.
    Client connects with ?token=<jwt_access_token>.
    """
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    from app.domains.auth.jwt_handler import decode_token
    try:
        payload = decode_token(token, expected_type="access")
    except Exception:
        await ws.close(code=4003, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=4003, reason="Invalid token")
        return

    await ws_manager.connect(user_id, ws)
    try:
        # Keep connection alive — listen for pings / any client messages
        while True:
            data = await ws.receive_text()
            # Client can send "ping", we reply "pong"
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(user_id, ws)
