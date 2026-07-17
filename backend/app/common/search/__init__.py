"""可复用高级搜索框架（多字段 / 多条件 AND·OR / 排序）。

参考 spt-mes 生产订单列表：
- 后端用「字段注册表 + DSL 编译器」把前端传来的 FilterDsl 编译成 SQLAlchemy WHERE。
- 字段白名单确保只有声明过的列可被筛选/排序（安全）。

用法（在各列表 service / router 中）：
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("customer", adv_filter, {"user_id": uid})
    if clause is not None:
        base = base.where(clause)
    order = resolve_sort("customer", sort_by, sort_order, Customer.created_at.desc())
"""
from .errors import FilterError
from .compiler import parse_filter, compile_filter
from .registry import get_schema, get_registry, ResourceSchema
from .custom_fields import (
    entity_search_context, get_entity_custom_fields, invalidate as invalidate_custom_fields,
    ENTITY_RESOURCES,
)


def build_filter_clause(resource: str, raw_filter, ctx: dict | None = None):
    """把 FilterDsl（JSON 字符串或 dict）编译为 SQLAlchemy 条件；无条件时返回 None。"""
    schema = get_schema(resource)
    if schema is None:
        return None
    return compile_filter(schema, parse_filter(raw_filter), ctx or {})


def filter_clause_or_400(resource: str, raw_filter, ctx: dict | None = None):
    """同 build_filter_clause，但把 FilterError 转成 400 业务异常。"""
    from app.common.exceptions import BusinessException
    try:
        return build_filter_clause(resource, raw_filter, ctx)
    except FilterError as e:
        raise BusinessException(code=400, message=f"高级筛选条件无效：{e}")


def resolve_sort(resource: str, sort_by: str | None, sort_order: str | None, default=None):
    """把排序字段 key 映射为 order_by 表达式；非法/未声明时返回 default。

    注意：不要写 `resolve_sort(...) or default`——SQLAlchemy 表达式不支持布尔取值
    （`bool(clause)` 会抛 TypeError）。把默认排序作为第 4 个参数传入。
    """
    schema = get_schema(resource)
    clause = schema.sort_clause(sort_by, sort_order) if schema is not None else None
    return clause if clause is not None else default


# ---- 基于「已构建 schema」的入口（供含自定义字段的实体列表复用同一个增强 schema）----
def filter_clause_from_schema_or_400(schema, raw_filter, ctx: dict | None = None):
    """用已构建好的 schema（含自定义字段）把 FilterDsl 编译成条件；FilterError→400。"""
    if schema is None:
        return None
    from app.common.exceptions import BusinessException
    try:
        return compile_filter(schema, parse_filter(raw_filter), ctx or {})
    except FilterError as e:
        raise BusinessException(code=400, message=f"高级筛选条件无效：{e}")


def resolve_sort_from_schema(schema, sort_by: str | None, sort_order: str | None, default=None):
    """同 resolve_sort，但直接用已构建的 schema（支持 cf_* 自定义字段排序）。"""
    clause = schema.sort_clause(sort_by, sort_order) if schema is not None else None
    return clause if clause is not None else default


__all__ = [
    "FilterError", "parse_filter", "compile_filter", "ResourceSchema",
    "get_schema", "get_registry", "build_filter_clause", "filter_clause_or_400",
    "resolve_sort",
    "entity_search_context", "filter_clause_from_schema_or_400", "resolve_sort_from_schema",
    "get_entity_custom_fields", "invalidate_custom_fields", "ENTITY_RESOURCES",
]
