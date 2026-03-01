from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.ai_center.models import AiTask, AiResult, AiPromptTemplate
from app.domains.ai_center.schemas import (
    AiTaskCreate, AiTaskUpdate, AiResultCreate,
    AiPromptTemplateCreate, AiPromptTemplateUpdate,
)
from app.domains.audit.service import log_action


# ==================== AiTask ====================

async def list_tasks(db: AsyncSession, tenant_id: str, biz_type: str | None = None, biz_id: str | None = None, status: str | None = None):
    q = select(AiTask).where(AiTask.tenant_id == tenant_id)
    if biz_type:
        q = q.where(AiTask.biz_type == biz_type)
    if biz_id:
        q = q.where(AiTask.biz_id == biz_id)
    if status:
        q = q.where(AiTask.status == status)
    result = await db.execute(q.order_by(AiTask.created_at.desc()))
    return result.scalars().all()


async def get_task(db: AsyncSession, tenant_id: str, task_id: str) -> AiTask:
    t = (await db.execute(
        select(AiTask).where(AiTask.id == task_id, AiTask.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not t:
        raise BusinessException(code=NOT_FOUND, message="AI任务不存在")
    return t


async def create_task(db: AsyncSession, tenant_id: str, data: AiTaskCreate, user: dict) -> AiTask:
    task = AiTask(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"],
        created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="create", resource_type="ai_task", resource_id=task.id,
        summary=f"创建AI任务: {data.task_type}"
    )
    return task


async def update_task(db: AsyncSession, tenant_id: str, task_id: str, data: AiTaskUpdate) -> AiTask:
    task = await get_task(db, tenant_id, task_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(task, field, val)
    await db.commit()
    await db.refresh(task)
    return task


# ==================== AiResult ====================

async def get_result_by_task(db: AsyncSession, tenant_id: str, task_id: str) -> AiResult | None:
    return (await db.execute(
        select(AiResult).where(AiResult.ai_task_id == task_id, AiResult.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def create_result(db: AsyncSession, tenant_id: str, data: AiResultCreate) -> AiResult:
    result = AiResult(
        id=generate_uuid(), tenant_id=tenant_id,
        **data.model_dump(exclude_unset=True),
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


# ==================== AiPromptTemplate ====================

async def list_templates(db: AsyncSession, tenant_id: str, task_type: str | None = None):
    q = select(AiPromptTemplate).where(AiPromptTemplate.tenant_id == tenant_id)
    if task_type:
        q = q.where(AiPromptTemplate.task_type == task_type)
    result = await db.execute(q.order_by(AiPromptTemplate.created_at.desc()))
    return result.scalars().all()


async def get_template(db: AsyncSession, tenant_id: str, template_id: str) -> AiPromptTemplate:
    t = (await db.execute(
        select(AiPromptTemplate).where(AiPromptTemplate.id == template_id, AiPromptTemplate.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not t:
        raise BusinessException(code=NOT_FOUND, message="提示词模板不存在")
    return t


async def create_template(db: AsyncSession, tenant_id: str, data: AiPromptTemplateCreate, user: dict) -> AiPromptTemplate:
    template = AiPromptTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        **data.model_dump(exclude_unset=True),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="create", resource_type="ai_prompt_template", resource_id=template.id,
        summary=f"创建提示词模板: {data.name}"
    )
    return template


async def update_template(db: AsyncSession, tenant_id: str, template_id: str, data: AiPromptTemplateUpdate) -> AiPromptTemplate:
    template = await get_template(db, tenant_id, template_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(template, field, val)
    await db.commit()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, tenant_id: str, template_id: str):
    template = await get_template(db, tenant_id, template_id)
    await db.delete(template)
    await db.commit()
