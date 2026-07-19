from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions
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


async def _load_task(db: AsyncSession, tenant_id: str, task_id: str, user: dict) -> UserTask:
    """按 id 取任务并校验数据范围。

    此前 update/delete 只按 tenant_id 取任务，列表里看不到的任务照样能按 id 改掉/删掉。
    可见口径与列表一致：本人负责/本人创建，或负责人落在自己的数据范围内（dept 档看下属）。
    """
    from app.common.exceptions import BusinessException
    from app.common.error_codes import FORBIDDEN
    from app.common.data_scope import resolve_owner_scope

    t = (await db.execute(
        select(UserTask).where(UserTask.tenant_id == tenant_id, UserTask.id == task_id)
    )).scalar()
    if not t:
        raise BusinessException(message="任务不存在")
    uid = user.get("sub")
    if t.assignee_id == uid or t.created_by_id == uid:
        return t
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None or (t.assignee_id and t.assignee_id in scope):
        return t
    raise BusinessException(code=FORBIDDEN, message="无权访问该任务（不在您的数据范围内）")


async def _scope_clause(db: AsyncSession, tenant_id: str, user: dict):
    """批量操作的范围约束；None 表示不限（管理员 / data_scope=all）。"""
    from app.common.data_scope import resolve_owner_scope
    scope = await resolve_owner_scope(db, user, tenant_id)
    if scope is None:
        return None
    uid = user.get("sub")
    return or_(
        UserTask.assignee_id.in_(scope),
        UserTask.assignee_id == uid,
        UserTask.created_by_id == uid,
    )


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
    current_user: dict = Depends(get_current_user),
):
    q = select(UserTask).where(UserTask.tenant_id == tenant_id)
    # By default show user's own tasks unless assignee_id is specified
    if assignee_id:
        # 显式按人筛选不能越权：assignee_id 必须落在自己的数据范围内，否则
        # 传个别人的 id 就绕过了默认的「只看自己」，把他的任务全列出来。
        from app.common.data_scope import resolve_owner_scope, scoped_owners
        scope = await resolve_owner_scope(db, current_user, tenant_id)
        allowed = scoped_owners(assignee_id, scope)
        if allowed:
            q = q.where(UserTask.assignee_id.in_(allowed))
        else:  # 目标不在范围内：只剩下「我派给他的」那部分可见
            q = q.where(UserTask.assignee_id == assignee_id,
                        UserTask.created_by_id == current_user["sub"])
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
    current_user: dict = Depends(get_current_user),
):
    from datetime import date as date_type
    parsed_due = None
    if body.due_date:
        parsed_due = date_type.fromisoformat(body.due_date)
    t = UserTask(
        tenant_id=tenant_id,
        title=body.title, description=body.description,
        due_date=parsed_due, priority=body.priority or "normal",
        assignee_id=body.assignee_id or current_user["sub"],
        assignee_name=body.assignee_name or current_user.get("real_name") or current_user.get("username"),
        created_by_id=current_user["sub"],
        created_by_name=current_user.get("real_name") or current_user.get("username"),
        biz_type=body.biz_type, biz_id=body.biz_id, biz_name=body.biz_name,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    # 分配给他人时，给被分配人发"任务待办"通知（自己给自己建任务不通知）
    if t.assignee_id and t.assignee_id != current_user["sub"]:
        try:
            from app.common.auto_notify import notify_task_assigned
            await notify_task_assigned(
                db, tenant_id, t.title, t.assignee_id,
                current_user.get("real_name") or current_user.get("username"), t.id,
            )
        except Exception:
            pass
    return ok(_task_dict(t))


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    t = await _load_task(db, tenant_id, task_id, current_user)
    data = body.model_dump(exclude_unset=True)
    if "due_date" in data and data["due_date"]:
        from datetime import date as date_type
        data["due_date"] = date_type.fromisoformat(data["due_date"])
    for k, v in data.items():
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
    current_user: dict = Depends(get_current_user),
):
    t = await _load_task(db, tenant_id, task_id, current_user)
    await db.delete(t)
    await db.commit()
    return ok()


# ---- Batch Operations ----


class BatchAssignBody(BaseModel):
    ids: list[str]
    assignee_id: str
    assignee_name: Optional[str] = None


class BatchCompleteBody(BaseModel):
    ids: list[str]


@router.post("/batch_assign")
async def batch_assign(
    body: BatchAssignBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Batch assign tasks to a user."""
    from sqlalchemy import update
    # 批量改派此前是裸 UPDATE ... WHERE id IN (...)，只认 tenant：
    # 拼一串别人的任务 id 就能整批改派。这里补上与列表一致的范围约束。
    scope_clause = await _scope_clause(db, tenant_id, current_user)
    conds = [UserTask.tenant_id == tenant_id, UserTask.id.in_(body.ids)]
    if scope_clause is not None:
        conds.append(scope_clause)
    # 取一个任务标题用于通知文案（在更新前读取）
    sample = (await db.execute(select(UserTask).where(*conds).limit(1))).scalar()
    result = await db.execute(
        update(UserTask).where(*conds)
        .values(assignee_id=body.assignee_id, assignee_name=body.assignee_name)
    )
    await db.commit()
    # 批量分配给他人时，给被分配人发一条汇总通知
    if body.assignee_id and body.assignee_id != current_user["sub"] and result.rowcount and sample:
        try:
            from app.common.auto_notify import notify_task_assigned
            await notify_task_assigned(
                db, tenant_id, sample.title, body.assignee_id,
                current_user.get("real_name") or current_user.get("username"),
                sample.id, count=result.rowcount,
            )
        except Exception:
            pass
    return ok({"updated": result.rowcount})


@router.post("/batch_complete")
async def batch_complete(
    body: BatchCompleteBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Batch mark tasks as completed."""
    from sqlalchemy import update
    # 同 batch_assign：裸 UPDATE 只认 tenant，等于任何人都能把别人的任务标记完成
    scope_clause = await _scope_clause(db, tenant_id, current_user)
    conds = [UserTask.tenant_id == tenant_id, UserTask.id.in_(body.ids)]
    if scope_clause is not None:
        conds.append(scope_clause)
    result = await db.execute(
        update(UserTask).where(*conds).values(is_completed=True, status="done")
    )
    await db.commit()
    return ok({"updated": result.rowcount})
