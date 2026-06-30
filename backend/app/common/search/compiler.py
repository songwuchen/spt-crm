"""把前端的 FilterDsl 编译成 SQLAlchemy 条件。

FilterDsl 结构：
    {
      "match": "all" | "any",          # AND / OR，默认 all
      "rules": [
        {"field": "status", "op": "in", "value": ["draft", "sent"]},
        {"field": "name", "op": "contains", "value": "ACME"},
        {"field": "created_at", "op": "relative", "value": "last7"}
      ]
    }
"""
import json

from sqlalchemy import and_, or_

from .errors import FilterError

MAX_RULES = 30


def parse_filter(raw):
    """接受 JSON 字符串或 dict，返回 dict 或 None。"""
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise FilterError("筛选条件 JSON 解析失败")
    if not isinstance(parsed, dict):
        raise FilterError("筛选条件应为对象")
    return parsed


def compile_filter(schema, dsl, ctx=None):
    """返回 SQLAlchemy 条件；无有效条件时返回 None。"""
    if not dsl:
        return None
    rules = dsl.get("rules") or []
    if not rules:
        return None
    if len(rules) > MAX_RULES:
        raise FilterError(f"筛选条件过多（最多 {MAX_RULES} 条）")
    match = (dsl.get("match") or "all").lower()
    clauses = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        fkey = r.get("field")
        op = r.get("op")
        if not fkey or not op:
            continue
        field = schema.field(fkey)
        if field is None:
            raise FilterError(f"未知筛选字段：{fkey}")
        clause = field.build(op, r.get("value"), ctx or {})
        if clause is not None:
            clauses.append(clause)
    if not clauses:
        return None
    return or_(*clauses) if match == "any" else and_(*clauses)
