"""字段类型定义 —— 每种字段知道：支持哪些操作符、如何渲染 schema、如何编译成 SQL 条件。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import or_, and_

from .errors import FilterError


# ---- 操作符集合（按字段类型）----
TEXT_OPS = ["contains", "not_contains", "eq", "ne", "starts_with", "ends_with", "in", "is_empty", "is_not_empty"]
NUMBER_OPS = ["eq", "ne", "gt", "gte", "lt", "lte", "between", "in", "is_empty", "is_not_empty"]
DATE_OPS = ["eq", "between", "before", "after", "relative", "is_empty", "is_not_empty"]
ENUM_OPS = ["eq", "ne", "in", "not_in", "is_empty", "is_not_empty"]
BOOL_OPS = ["eq"]
RELATION_OPS = ["eq", "ne", "in", "is_empty", "is_not_empty"]
PEOPLE_OPS = ["eq", "ne", "in", "me", "is_empty", "is_not_empty"]


# ---- 值解析辅助 ----
def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip() != ""]
    return [x.strip() for x in str(value).replace("，", ",").split(",") if x.strip()]


def _as_pair(value):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    raise FilterError("区间需要两个值 [最小, 最大]")


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        raise FilterError(f"需要数字，收到：{v!r}")


def _esc_like(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _add_month(d: date, delta: int = 1) -> date:
    m = d.month - 1 + delta
    y = d.year + m // 12
    return date(y, m % 12 + 1, 1)


def _relative_range(token: str):
    """把相对时间 token 转成 [start, end)（end 为开区间，均为 date）。"""
    today = date.today()
    t = (token or "").strip()
    if t == "today":
        return today, today + timedelta(days=1)
    if t == "yesterday":
        return today - timedelta(days=1), today
    if t == "last7":
        return today - timedelta(days=6), today + timedelta(days=1)
    if t == "last30":
        return today - timedelta(days=29), today + timedelta(days=1)
    if t == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7)
    if t == "this_month":
        start = today.replace(day=1)
        return start, _add_month(start, 1)
    if t == "last_month":
        start = _add_month(today.replace(day=1), -1)
        return start, today.replace(day=1)
    if t == "this_year":
        return date(today.year, 1, 1), date(today.year + 1, 1, 1)
    raise FilterError(f"未知相对时间：{token}")


# ---- 字段基类 ----
class Field:
    type = "text"
    default_ops = TEXT_OPS

    def __init__(self, key, label, column, *, operators=None, options=None,
                 option_source=None, sortable=True):
        self.key = key
        self.label = label
        self.column = column
        self.operators = list(operators) if operators else list(self.default_ops)
        self.options = options          # list[(value, label)]
        self.option_source = option_source  # e.g. "users" — 前端去对应接口拉取选项
        self.sortable = sortable

    def schema(self) -> dict:
        d = {"key": self.key, "label": self.label, "type": self.type,
             "operators": self.operators, "sortable": self.sortable}
        if self.options is not None:
            d["options"] = [{"value": v, "label": l} for v, l in self.options]
        if self.option_source:
            d["optionSource"] = self.option_source
        return d

    def _empty_clause(self, negate=False):
        return self.column.isnot(None) if negate else self.column.is_(None)

    def build(self, op, value, ctx):
        if op not in self.operators:
            raise FilterError(f"字段「{self.label}」不支持操作符 {op}")
        if op == "is_empty":
            return self._empty_clause()
        if op == "is_not_empty":
            return self._empty_clause(negate=True)
        return self._build(op, value, ctx)

    def _build(self, op, value, ctx):  # pragma: no cover - overridden
        raise FilterError(f"字段「{self.label}」不支持操作符 {op}")


class TextField(Field):
    type = "text"
    default_ops = TEXT_OPS

    def _empty_clause(self, negate=False):
        if negate:
            return and_(self.column.isnot(None), self.column != "")
        return or_(self.column.is_(None), self.column == "")

    def _build(self, op, value, ctx):
        if op == "in":
            vals = _as_list(value)
            if not vals:
                raise FilterError(f"「{self.label}」需要至少一个值")
            return self.column.in_(vals)
        if value is None or str(value).strip() == "":
            raise FilterError(f"「{self.label}」需要一个值")
        s = str(value)
        if op == "contains":
            return self.column.ilike(f"%{_esc_like(s)}%", escape="\\")
        if op == "not_contains":
            return or_(self.column.is_(None), ~self.column.ilike(f"%{_esc_like(s)}%", escape="\\"))
        if op == "starts_with":
            return self.column.ilike(f"{_esc_like(s)}%", escape="\\")
        if op == "ends_with":
            return self.column.ilike(f"%{_esc_like(s)}", escape="\\")
        if op == "eq":
            return self.column == s
        if op == "ne":
            return self.column != s
        raise FilterError(f"「{self.label}」不支持操作符 {op}")


class NumberField(Field):
    type = "number"
    default_ops = NUMBER_OPS

    def _build(self, op, value, ctx):
        if op == "in":
            vals = [_num(x) for x in _as_list(value)]
            if not vals:
                raise FilterError(f"「{self.label}」需要至少一个值")
            return self.column.in_(vals)
        if op == "between":
            lo, hi = _as_pair(value)
            return and_(self.column >= _num(lo), self.column <= _num(hi))
        n = _num(value)
        return {
            "eq": self.column == n, "ne": self.column != n,
            "gt": self.column > n, "gte": self.column >= n,
            "lt": self.column < n, "lte": self.column <= n,
        }[op]


class DateField(Field):
    type = "date"
    default_ops = DATE_OPS

    def __init__(self, *a, is_datetime=False, **k):
        super().__init__(*a, **k)
        self.is_datetime = is_datetime
        if is_datetime:
            self.type = "datetime"

    def _coerce(self, s) -> date:
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
        except ValueError:
            raise FilterError("日期格式应为 YYYY-MM-DD")

    def _bound(self, d: date):
        return datetime(d.year, d.month, d.day) if self.is_datetime else d

    def _build(self, op, value, ctx):
        if op == "relative":
            start, end = _relative_range(str(value))
            return and_(self.column >= self._bound(start), self.column < self._bound(end))
        if op == "between":
            lo, hi = _as_pair(value)
            d1, d2 = self._coerce(lo), self._coerce(hi)
            return and_(self.column >= self._bound(d1), self.column < self._bound(d2 + timedelta(days=1)))
        d = self._coerce(value)
        if op == "eq":
            return and_(self.column >= self._bound(d), self.column < self._bound(d + timedelta(days=1)))
        if op == "before":
            return self.column < self._bound(d)
        if op == "after":
            return self.column >= self._bound(d + timedelta(days=1))
        raise FilterError(f"「{self.label}」不支持操作符 {op}")


class EnumField(Field):
    type = "enum"
    default_ops = ENUM_OPS

    def _validate(self, v) -> str:
        s = str(v)
        if self.options is not None:
            allowed = {str(val) for val, _ in self.options}
            if s not in allowed:
                raise FilterError(f"「{self.label}」非法选项：{v}")
        return s

    def _build(self, op, value, ctx):
        if op in ("in", "not_in"):
            vals = [self._validate(x) for x in _as_list(value)]
            if not vals:
                raise FilterError(f"「{self.label}」需要至少一个值")
            clause = self.column.in_(vals)
            return ~clause if op == "not_in" else clause
        v = self._validate(value)
        if op == "eq":
            return self.column == v
        if op == "ne":
            return self.column != v
        raise FilterError(f"「{self.label}」不支持操作符 {op}")


class BooleanField(Field):
    type = "boolean"
    default_ops = BOOL_OPS

    def _build(self, op, value, ctx):
        truthy = value in (True, "true", "True", "1", 1)
        return self.column.is_(True) if truthy else or_(self.column.is_(False), self.column.is_(None))


class RelationField(Field):
    type = "relation"
    default_ops = RELATION_OPS

    def _build(self, op, value, ctx):
        if op == "in":
            vals = _as_list(value)
            if not vals:
                raise FilterError(f"「{self.label}」需要至少一个值")
            return self.column.in_(vals)
        if op == "eq":
            return self.column == str(value)
        if op == "ne":
            return self.column != str(value)
        raise FilterError(f"「{self.label}」不支持操作符 {op}")


class PeopleField(Field):
    type = "people"
    default_ops = PEOPLE_OPS

    def _build(self, op, value, ctx):
        if op == "me":
            uid = (ctx or {}).get("user_id")
            return self.column == uid
        if op == "in":
            vals = _as_list(value)
            if not vals:
                raise FilterError(f"「{self.label}」需要至少一个值")
            return self.column.in_(vals)
        if op == "eq":
            return self.column == str(value)
        if op == "ne":
            return self.column != str(value)
        raise FilterError(f"「{self.label}」不支持操作符 {op}")
