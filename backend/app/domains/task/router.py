from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.task.models import UserTask

router = APIRouter(prefix="/api/v1/tasks", tags=["任务管理"])


class TaskCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = Field("normal", pattern=r"^(low|normal|high|urgent)$")
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None
    biz_name: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    is_completed: Optional[bool] = None


def _task_dict(t) -> dict:
    return {
        "id": t.id, "title": t.title, "description": t.description,
        "due_date": str(t.due_date) if t.due_date else None,
        "priority": t.priority, "status": t.status,
        "assignee_id": t.assignee_id, "assignee_name": t.assignee_name,
        "created_by_id": t.created_by_id, "created_by_name": t.created_by_name,
        "biz_type": t.biz_type, "biz_id": t.biz_id, "biz_name": t.biz_name,
        "is_completed": t.is_completed,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


@router.get("")
async def list_tasks(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    priority: str = Query(None),
    assignee_id: str = Query(None),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    q = select(UserTask).where(UserTask.tenant_id == tenant_id)
    # By default show user's own tasks unless assignee_id is specified
    if assignee_id:
        q = q.where(UserTask.assignee_id == assignee_id)
    else:
        q = q.where(or_(UserTask.assignee_id == current_user["sub"], UserTask.created_by_id == current_user["sub"]))
    if status:
        q = q.where(UserTask.status == status)
    if priority:
        q = q.where(UserTask.priority == priority)
    if keyword:
        q = q.where(UserTask.title.ilike(f"%{keyword}%"))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (await db.execute(
        q.order_by(UserTask.due_date.asc().nullslast(), UserTask.created_at.desc())
        .offset((pageNo - 1) * pageSize).limit(pageSize)
    )).scalars().all()
    return ok({"items": [_task_dict(t) for t in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("")
async def create_task(
    body: TaskCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    t = UserTask(
        tenant_id=tenant_id,
        title=body.title, description=body.description,
        due_date=body.due_date, priority=body.priority or "normal",
        assignee_id=body.assignee_id or current_user["sub"],
        assignee_name=body.assignee_name or current_user.get("real_name") or current_user.get("username"),
        created_by_id=current_user["sub"],
        created_by_name=current_user.get("real_name") or current_user.get("username"),
        biz_type=body.biz_type, biz_id=body.biz_id, biz_name=body.biz_name,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return ok(_task_dict(t))


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    from app.common.exceptions import BusinessException
    t = (await db.execute(
        select(UserTask).where(UserTask.tenant_id == tenant_id, UserTask.id == task_id)
    )).scalar()
    if not t:
        raise BusinessException("任务不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    if body.is_completed is True:
        t.status = "done"
    await db.commit()
    await db.refresh(t)
    return ok(_task_dict(t))


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions()),
):
    from app.common.exceptions import BusinessException
    t = (await db.execute(
        select(UserTask).where(UserTask.tenant_id == tenant_id, UserTask.id == task_id)
    )).scalar()
    if not t:
        raise BusinessException("任务不存在")
    await db.delete(t)
    await db.commit()
    return ok()
