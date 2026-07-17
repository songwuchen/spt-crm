"""把低代码「扩展字段」(存于各业务表 custom_fields_json) 接入高级搜索。

字段定义来自表单引擎(lowcode.get_entity_fields)已发布版本;这里把每个可筛选字段
映射为 fields.py 里的 Field 实例(key 统一 cf_<field_id>),从而复用其「操作符→SQL」
能力。标量字段直接把 JSON 取值表达式当作 column;多值(数组)字段用 JsonArrayField
以 jsonb 包含语义实现。

安全:custom_fields_json 是 sa.JSON(PG json)。数字/日期按文本取出后带正则守卫再 cast,
脏数据取 NULL 而非抛错(筛选与 ORDER BY 都安全);多值用 jsonb `@>` 包含判断。
"""
from __future__ import annotations

import time

from sqlalchemy import Date, Numeric, and_, case, cast, func, not_, or_
from sqlalchemy.dialects.postgresql import JSONB

from .errors import FilterError
from .fields import (
    Field, TextField, NumberField, DateField, EnumField, BooleanField,
    PeopleField, RelationField, _as_list,
)
from .registry import get_schema


# ---- JSON 取值表达式（PG 运算符，兼容 json/jsonb）----
def _txt(col, fid):
    """custom_fields_json ->> 'fid' —— 以文本取出。"""
    return col.op("->>")(fid)


def _num_expr(col, fid):
    """数字取值：仅当文本形如数字才 cast，否则 NULL（避免脏数据 cast 报错）。"""
    t = _txt(col, fid)
    return case((t.op("~")(r"^-?[0-9]+(\.[0-9]+)?$"), cast(t, Numeric)), else_=None)


def _date_expr(col, fid):
    """日期取值：取前 10 位形如 YYYY-MM-DD 才 cast，否则 NULL。"""
    t = _txt(col, fid)
    return case((t.op("~")(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"),
                 cast(func.substr(t, 1, 10), Date)), else_=None)


def _bool_expr(col, fid):
    """开关取值：JSON true/false → 布尔，其余 NULL。"""
    t = _txt(col, fid)
    return case((t.in_(("true", "t", "1")), True),
                (t.in_(("false", "f", "0")), False), else_=None)


def _extract_options(fd: dict):
    """把字段定义的 options 归一为 [(value, label)]。"""
    out = []
    for o in fd.get("options") or []:
        if isinstance(o, dict):
            val = o.get("value", o.get("key"))
            if val is None:
                continue
            out.append((str(val), str(o.get("label", val))))
        else:
            out.append((str(o), str(o)))
    return out or None


# ---- 多值(数组)字段：jsonb 包含语义 ----
_ARRAY_OPS = ["contains", "not_contains", "in", "is_empty", "is_not_empty"]


class JsonArrayField(Field):
    """multi_select / checkbox / person_multi / department_multi —— 值是数组，
    「包含」用 jsonb `@>` 判断。不支持排序。"""

    def __init__(self, key, label, col, fid, *, schema_type="enum",
                 options=None, option_source=None, with_me=False):
        ops = list(_ARRAY_OPS)
        if with_me:
            ops.insert(3, "me")
        super().__init__(key, label, None, operators=ops, options=options,
                         option_source=option_source, sortable=False)
        self.type = schema_type
        self._col = col
        self._fid = fid

    def _jsonb(self):
        return cast(self._col.op("->")(self._fid), JSONB)

    def _raw(self):
        return self._col.op("->>")(self._fid)

    def _contains(self, v):
        # 用 jsonb_build_array 在库内构造 jsonb 数组(值作为 text 绑定)，
        # 避免把 JSONB 型参数交给驱动导致二次编码（asyncpg 会把字符串再 json 化）。
        return self._jsonb().op("@>")(func.jsonb_build_array(str(v)))

    def _empty_clause(self, negate=False):
        t = self._raw()
        if negate:
            return and_(t.isnot(None), t.notin_(("", "[]")))
        return or_(t.is_(None), t.in_(("", "[]")))

    def _build(self, op, value, ctx):
        if op == "me":
            uid = (ctx or {}).get("user_id")
            if not uid:
                raise FilterError("无法确定当前用户")
            return self._contains(uid)
        if op == "in":
            vals = _as_list(value)
            if not vals:
                raise FilterError(f"「{self.label}」需要至少一个值")
            return or_(*[self._contains(v) for v in vals])
        if value is None or str(value).strip() == "":
            raise FilterError(f"「{self.label}」需要一个值")
        c = self._contains(value)
        if op == "contains":
            return c
        if op == "not_contains":
            return or_(self._raw().is_(None), not_(c))
        raise FilterError(f"「{self.label}」不支持操作符 {op}")


# ---- 低代码 FieldType → Field ----
def build_entity_custom_fields(entity_type: str, field_defs: list[dict], model) -> list[Field]:
    """把已发布字段定义映射为可筛选/排序的 Field 列表(跳过非标量/不支持类型)。"""
    col = model.custom_fields_json
    out: list[Field] = []
    for fd in field_defs or []:
        fid = fd.get("id")
        ftype = fd.get("type")
        if not fid or not ftype:
            continue
        label = fd.get("label") or fid
        key = f"cf_{fid}"
        opts = _extract_options(fd)
        if ftype in ("text", "textarea", "rich_text", "auto_number"):
            out.append(TextField(key, label, _txt(col, fid)))
        elif ftype in ("number", "amount", "formula"):
            out.append(NumberField(key, label, _num_expr(col, fid)))
        elif ftype in ("date", "datetime"):
            out.append(DateField(key, label, _date_expr(col, fid), is_datetime=(ftype == "datetime")))
        elif ftype in ("select", "radio"):
            out.append(EnumField(key, label, _txt(col, fid), options=opts))
        elif ftype == "switch":
            out.append(BooleanField(key, label, _bool_expr(col, fid)))
        elif ftype == "person":
            out.append(PeopleField(key, label, _txt(col, fid), option_source="users"))
        elif ftype == "department":
            out.append(RelationField(key, label, _txt(col, fid), option_source="departments"))
        elif ftype in ("multi_select", "checkbox"):
            out.append(JsonArrayField(key, label, col, fid, schema_type="enum", options=opts))
        elif ftype == "person_multi":
            out.append(JsonArrayField(key, label, col, fid, schema_type="people",
                                      option_source="users", with_me=True))
        elif ftype == "department_multi":
            out.append(JsonArrayField(key, label, col, fid, schema_type="relation",
                                      option_source="departments"))
        # 其余(detail_table/sub_table_data/file/image/signature/related_doc/
        # location/address/cascade/select_data/relation)不支持筛选，跳过。
    return out


# ---- 实体 → 模型(懒加载避免导入环) ----
def _entity_model(entity_type: str):
    from app.domains.customer.models import Customer, Contact
    from app.domains.lead.models import Lead
    from app.domains.project.models import OpportunityProject
    from app.domains.order.models import Order
    from app.domains.service_ticket.models import ServiceTicket
    from app.domains.contract.models import Contract
    try:
        from app.domains.quote.models import Quote
    except Exception:  # pragma: no cover
        Quote = None
    try:
        from app.domains.payment.models import PaymentRecord
    except Exception:  # pragma: no cover
        PaymentRecord = None
    mapping = {
        "customer": Customer, "contact": Contact, "lead": Lead,
        "project": OpportunityProject, "order": Order,
        "service_ticket": ServiceTicket, "contract": Contract,
        "quote": Quote, "payment": PaymentRecord,
    }
    m = mapping.get(entity_type)
    # 尚未补 custom_fields_json 列的实体(如未迁移的 quote/payment)直接跳过
    if m is not None and not hasattr(m, "custom_fields_json"):
        return None
    return m


#: 拥有 custom_fields_json 扩展字段、需在高级搜索中合并自定义字段的资源
ENTITY_RESOURCES = {
    "customer", "lead", "project", "contact", "order",
    "service_ticket", "contract", "quote", "payment",
}


# ---- 进程内 TTL 缓存(字段定义)----
_CACHE: dict[tuple, tuple[float, list]] = {}
_TTL = 60.0


def invalidate(tenant_id: str | None = None, entity_type: str | None = None) -> None:
    """字段定义变化(发布)后清缓存。无参则全清。"""
    if tenant_id is None or entity_type is None:
        _CACHE.clear()
        return
    _CACHE.pop((tenant_id, entity_type), None)


async def get_entity_custom_fields(db, tenant_id: str, entity_type: str) -> list[Field]:
    """取该实体已发布扩展字段并构建 Field 列表(带 TTL 缓存)。"""
    model = _entity_model(entity_type)
    if model is None:
        return []
    ck = (tenant_id, entity_type)
    now = time.monotonic()
    hit = _CACHE.get(ck)
    if hit and now - hit[0] < _TTL:
        defs = hit[1]
    else:
        from app.domains.lowcode.service import get_entity_fields
        defs = await get_entity_fields(db, tenant_id, entity_type)
        _CACHE[ck] = (now, defs)
    return build_entity_custom_fields(entity_type, defs, model)


async def entity_search_context(resource: str, db, tenant_id: str):
    """返回「静态字段 + 自定义字段」合并后的 ResourceSchema(供筛选+排序共用)。"""
    schema = get_schema(resource)
    if schema is None:
        return None
    if resource in ENTITY_RESOURCES:
        extra = await get_entity_custom_fields(db, tenant_id, resource)
        if extra:
            schema = schema.with_extra(extra)
    return schema
