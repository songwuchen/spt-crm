from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.activity import service
from app.domains.activity.schemas import ActivityCreate, ActivityUpdate

router = APIRouter(tags=["互动记录"])


def _activity_dict(a) -> dict:
    return {
        "id": a.id,
        "biz_type": a.biz_type,
        "biz_id": a.biz_id,
        "activity_type": a.activity_type,
        "subject": a.subject,
        "content": a.content,
        "contact_name": a.contact_name,
        "result_json": a.result_json,
        "created_by_id": a.created_by_id,
        "created_by_name": a.created_by_name,
        "created_at": a.created_at.isoformat() if a.created_at else "",
        "updated_at": a.updated_at.isoformat() if a.updated_at else "",
    }


@router.get("/api/v1/activities")
async def list_activities(
    biz_type: str = Query(...), biz_id: str = Query(...),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    items = await service.list_activities(db, tenant_id, biz_type, biz_id)
    return ok([_activity_dict(a) for a in items])


@router.post("/api/v1/activities")
async def create_activity(
    body: ActivityCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    a = await service.create_activity(db, tenant_id, body, current_user)
    return ok(_activity_dict(a))


@router.put("/api/v1/activities/{activity_id}")
async def update_activity(
    activity_id: str, body: ActivityUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("customer:edit")),
):
    a = await service.update_activity(db, tenant_id, activity_id, body, current_user)
    return ok(_activity_dict(a))


@router.delete("/api/v1/activities/{activity_id}")
async def delete_activity(
    activity_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:edit")),
):
    await service.delete_activity(db, tenant_id, activity_id)
    return ok(None)


@router.post("/api/v1/activities/ai-summary")
async def ai_summarize_activities(
    biz_type: str = Query(...), biz_id: str = Query(...),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    """Generate an AI summary of recent activities for a business entity."""
    items = await service.list_activities(db, tenant_id, biz_type, biz_id)
    activities = [_activity_dict(a) for a in items[:30]]
    from app.common.ai_engine import summarize_activity
    result = await summarize_activity(activities)
    return ok(result)
