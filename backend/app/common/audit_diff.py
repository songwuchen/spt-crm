"""字段级变更 diff，供审计日志 / 数据日志使用。"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def serialize_value(val: Any) -> Any:
    """将值转为可 JSON 序列化、便于前端展示的形式。"""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, (list, tuple)):
        return [serialize_value(v) for v in val]
    if isinstance(val, dict):
        return {str(k): serialize_value(v) for k, v in val.items()}
    return str(val)


def _values_equal(a: Any, b: Any) -> bool:
    return serialize_value(a) == serialize_value(b)


def compute_dict_changes(
    old: dict | None,
    new: dict | None,
    *,
    prefix: str = "",
    skip_keys: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """对比两个字典，返回 {key: {old, new}}。"""
    skip = skip_keys or set()
    old = old or {}
    new = new or {}
    changes: dict[str, dict[str, Any]] = {}
    for key in set(old) | set(new):
        if key in skip:
            continue
        ov, nv = old.get(key), new.get(key)
        if _values_equal(ov, nv):
            continue
        field_key = f"{prefix}{key}" if prefix else str(key)
        changes[field_key] = {"old": serialize_value(ov), "new": serialize_value(nv)}
    return changes


def compute_entity_changes(
    entity: Any,
    update_data: dict[str, Any],
    *,
    json_fields: set[str] | None = None,
    exclude_fields: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """对比 ORM 实体与待更新字段，自动展开 JSON 列内层 diff。"""
    json_fields = json_fields or set()
    exclude = exclude_fields or set()
    changes: dict[str, dict[str, Any]] = {}

    for field, val in update_data.items():
        if field in exclude:
            continue
        if field in json_fields and isinstance(val, dict):
            old_json = getattr(entity, field, None) or {}
            nested = compute_dict_changes(old_json, val, prefix=f"{field}.")
            changes.update(nested)
            continue
        old_val = getattr(entity, field, None)
        if _values_equal(old_val, val):
            continue
        changes[field] = {"old": serialize_value(old_val), "new": serialize_value(val)}

    return changes


def enrich_changes_with_labels(
    changes: dict[str, dict[str, Any]],
    labels: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """为每条变更附加 field_label（供前端直接展示）。"""
    enriched: dict[str, dict[str, Any]] = {}
    for key, diff in changes.items():
        entry = dict(diff)
        entry["label"] = labels.get(key) or labels.get(key.split(".")[-1]) or key
        enriched[key] = entry
    return enriched


def labels_from_field_defs(field_defs: list[dict[str, Any]] | None) -> dict[str, str]:
    """从低代码字段定义提取 id → label 映射。"""
    if not field_defs:
        return {}
    out: dict[str, str] = {}
    for fd in field_defs:
        fid = fd.get("id")
        label = fd.get("label")
        if fid and label:
            out[str(fid)] = str(label)
    return out
