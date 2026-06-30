"""高级搜索字段 schema 接口 —— 前端据此渲染条件构建器。"""
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from .registry import get_schema

router = APIRouter(prefix="/api/v1/search-schema", tags=["高级搜索"])


@router.get("/{resource}")
async def get_resource_schema(resource: str, _user: dict = Depends(get_current_user)):
    schema = get_schema(resource)
    if schema is None:
        raise BusinessException(code=404, message="未知资源")
    return ok(schema.schema_dict())
