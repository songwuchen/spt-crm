"""高级搜索字段 schema 接口 —— 前端据此渲染条件构建器。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, get_tenant_id
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from .registry import get_schema
from .custom_fields import ENTITY_RESOURCES, get_entity_custom_fields

router = APIRouter(prefix="/api/v1/search-schema", tags=["高级搜索"])


@router.get("/{resource}")
async def get_resource_schema(
    resource: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    schema = get_schema(resource)
    if schema is None:
        raise BusinessException(code=404, message="未知资源")
    # 实体资源：把已发布的自定义(扩展)字段并入 schema，前端高级筛选即可用。
    if resource in ENTITY_RESOURCES:
        extra = await get_entity_custom_fields(db, tenant_id, resource)
        if extra:
            schema = schema.with_extra(extra)
    return ok(schema.schema_dict())
