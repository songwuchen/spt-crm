from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.activity import service
from app.domains.activity.models import Activity
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
        "contact_id": a.contact_id,
        "contact_name": a.contact_name,
        "result_json": a.result_json,
        "next_follow_date": str(a.next_follow_date) if a.next_follow_date else None,
        "biz_name": a.biz_name,
        "mentions_json": a.mentions_json,
        "pinned": bool(a.pinned) if a.pinned else False,
        "created_by_id": a.created_by_id,
        "created_by_name": a.created_by_name,
        "created_at": a.created_at.isoformat() if a.created_at else "",
        "updated_at": a.updated_at.isoformat() if a.updated_at else "",
    }


@router.get("/api/v1/activities/all")
async def list_all_activities(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    biz_type: str = Query(None),
    activity_type: str = Query(None),
    keyword: str = Query(None),
    created_by_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    """List all activities across biz types with pagination and filters."""
    q = select(Activity).where(Activity.tenant_id == tenant_id)
    count_q = select(func.count(Activity.id)).where(Activity.tenant_id == tenant_id)

    if biz_type:
        q = q.where(Activity.biz_type == biz_type)
        count_q = count_q.where(Activity.biz_type == biz_type)
    if activity_type:
        q = q.where(Activity.activity_type == activity_type)
        count_q = count_q.where(Activity.activity_type == activity_type)
    if created_by_id:
        q = q.where(Activity.created_by_id == created_by_id)
        count_q = count_q.where(Activity.created_by_id == created_by_id)
    if keyword:
        kw = f"%{keyword}%"
        flt = or_(
            Activity.subject.ilike(kw), Activity.content.ilike(kw),
            Activity.contact_name.ilike(kw), Activity.biz_name.ilike(kw),
            Activity.created_by_name.ilike(kw),
        )
        q = q.where(flt)
        count_q = count_q.where(flt)

    # 数据范围：此前只按 tenant 过滤，业务员能刷到全公司的跟进流（客户名、联系人、谈话内容）
    scope_clause = await service.visible_activity_clause(db, tenant_id, _user)
    if scope_clause is not None:
        q = q.where(scope_clause)
        count_q = count_q.where(scope_clause)

    total = (await db.execute(count_q)).scalar() or 0
    items = (await db.execute(
        q.order_by(Activity.created_at.desc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).scalars().all()

    return ok({
        "items": [_activity_dict(a) for a in items],
        "total": total,
        "pageNo": pageNo,
        "pageSize": pageSize,
    })


@router.get("/api/v1/activities")
async def list_activities(
    biz_type: str = Query(...), biz_id: str = Query(...),
    pageSize: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    items = await service.list_activities(db, tenant_id, biz_type, biz_id, limit=pageSize, offset=offset, user=_user)
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
    await service.delete_activity(db, tenant_id, activity_id, _user)
    return ok(None)


@router.post("/api/v1/activities/{activity_id}/pin")
async def toggle_pin(
    activity_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:edit")),
):
    a = await service.get_activity(db, tenant_id, activity_id, _user)
    a.pinned = not bool(a.pinned)
    await db.commit()
    await db.refresh(a)
    return ok(_activity_dict(a))


@router.post("/api/v1/activities/ai-summary")
async def ai_summarize_activities(
    biz_type: str = Query(...), biz_id: str = Query(...),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("customer:view")),
):
    """Generate an AI summary of recent activities for a business entity."""
    items = await service.list_activities(db, tenant_id, biz_type, biz_id, user=_user)
    activities = [_activity_dict(a) for a in items[:30]]
    from app.common.ai_engine import summarize_activity
    result = await summarize_activity(activities)
    return ok(result)
