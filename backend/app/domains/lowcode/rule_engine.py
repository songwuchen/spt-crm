"""表单规则引擎(Python 侧) —— 与前端 RuleEngine.ts 严格对等的移植。

后端必须自己会算规则，原因有二：
1. 规则只跑在前端时，直接调 API 即可绕过「条件必填」；
2. 更隐蔽的是死锁 —— 字段静态 required=True、又被显隐规则藏起来时，前端跳过校验、
   后端却照样拦，用户会看到「界面上根本不存在的字段报必填」且无从修复。

因此 required 的判定必须建立在「先算显隐、再校验」之上，两端用同一套语义。
改这里时请同步改 frontend/src/components/lowcode/RuleEngine.ts，反之亦然。

已知的刻意分歧：JS `Number([5])` 为 5、`Number([])` 为 0，本实现对 list/dict 一律取 NaN
（即数值比较不成立）。仅影响「对数组字段做 gt/lt 比较」这种无意义组合。
"""
from __future__ import annotations

import json
import math
from typing import Any, Iterable, Mapping

NAN = float("nan")

# 与前端 FieldState 对齐
FieldStates = dict[str, dict[str, bool]]


# ===== JS 语义辅助：保证与前端逐位对齐 =====

def _js_number(v: Any) -> float:
    """近似 JS Number()：None→0、bool→0/1、空串/空白→0、非数字串→NaN。"""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return NAN
    return NAN


def _js_str(v: Any) -> str:
    """近似 JS String()：bool→'true'/'false'、整数值浮点不带小数、list→逗号连接。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, (list, tuple)):
        return ",".join(_js_str(x) for x in v)
    if v is None:
        return "null"
    if isinstance(v, str):
        return v
    return str(v)


def _loose_equal(a: Any, b: Any) -> bool:
    if a is b:
        return True
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return json.dumps(sorted(_js_str(x) for x in a)) == json.dumps(sorted(_js_str(x) for x in b))
    # 数值/布尔/字符串一律按 JS 的字符串化后比较（'5' == 5 成立，与前端一致）
    return _js_str(a) == _js_str(b)


def _is_empty(v: Any) -> bool:
    """与前端 isEmpty 对齐：null/undefined、空串、空数组为空；0 与 false 不为空。"""
    if v is None:
        return True
    if isinstance(v, str) and v == "":
        return True
    if isinstance(v, (list, tuple)) and len(v) == 0:
        return True
    return False


def _compare(a: Any, b: Any) -> int:
    na, nb = _js_number(a), _js_number(b)
    if a != "" and b != "" and not math.isnan(na) and not math.isnan(nb):
        return -1 if na < nb else (1 if na > nb else 0)
    sa, sb = _js_str(a), _js_str(b)
    return -1 if sa < sb else (1 if sa > sb else 0)


def _as_list(expected: Any) -> list[Any]:
    if isinstance(expected, (list, tuple)):
        return list(expected)
    return [s.strip() for s in _js_str(expected if expected is not None else "").split(",") if s.strip()]


def _test_op(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return _loose_equal(actual, expected)
    if operator == "ne":
        return not _loose_equal(actual, expected)
    if operator == "is_empty":
        return _is_empty(actual)
    if operator == "is_not_empty":
        return not _is_empty(actual)
    if operator in ("gt", "gte", "lt", "lte"):
        if actual is None or actual == "":
            return False
        c = _compare(actual, expected)
        return {"gt": c > 0, "gte": c >= 0, "lt": c < 0, "lte": c <= 0}[operator]
    if operator in ("in", "not_in"):
        lst = _as_list(expected)
        if isinstance(actual, (list, tuple)):
            hit = any(any(_loose_equal(v, e) for e in lst) for v in actual)
        else:
            hit = any(_loose_equal(actual, e) for e in lst)
        return hit if operator == "in" else not hit
    if operator in ("contains", "not_contains"):
        if isinstance(actual, (list, tuple)):
            hit = any(_loose_equal(v, expected) for v in actual)
        else:
            hit = _js_str(expected if expected is not None else "") in _js_str(actual if actual is not None else "")
        return hit if operator == "contains" else not hit
    if operator == "starts_with":
        return _js_str(actual if actual is not None else "").startswith(_js_str(expected if expected is not None else ""))
    if operator == "ends_with":
        return _js_str(actual if actual is not None else "").endswith(_js_str(expected if expected is not None else ""))
    return False


# ===== 条件树求值 =====

def _sub_field_map(fields: list[dict]) -> dict[str, str]:
    """明细子表列 id -> 所属子表字段 id。"""
    out: dict[str, str] = {}
    for f in fields or []:
        for col in f.get("detail_table_columns") or []:
            out[col.get("id")] = f.get("id")
    return out


def _actuals(field: str, values: Mapping[str, Any], sub_map: Mapping[str, str]) -> list[Any]:
    """子表列取「每一行的该列值」（任一行匹配即命中）；普通字段取单值。"""
    parent = sub_map.get(field)
    if parent:
        rows = values.get(parent)
        if not isinstance(rows, (list, tuple)) or len(rows) == 0:
            return [None]
        return [r.get(field) if isinstance(r, Mapping) else None for r in rows]
    return [values.get(field)]


def _eval_single(field: str, operator: str, expected: Any, values, sub_map, hidden: Iterable[str]) -> bool:
    hidden = hidden or ()
    # 被隐藏的字段其值不参与判定（级联隐藏的关键）
    if field in hidden or sub_map.get(field) in hidden:
        return False
    return any(_test_op(a, operator, expected) for a in _actuals(field, values, sub_map))


def _eval_node(node: Any, values, sub_map, hidden) -> bool:
    if isinstance(node, Mapping) and isinstance(node.get("cond"), (list, tuple)):
        return _eval_group(node.get("rel") or "and", node["cond"], values, sub_map, hidden)
    if not isinstance(node, Mapping):
        return False
    if not node.get("field") or not node.get("operator"):
        return False
    return _eval_single(node["field"], node["operator"], node.get("value"), values, sub_map, hidden)


def _eval_group(rel: str, cond: list, values, sub_map, hidden) -> bool:
    if not cond:
        return rel == "and"
    results = (_eval_node(c, values, sub_map, hidden) for c in cond)
    return all(results) if rel == "and" else any(results)


def evaluate_condition(condition: Any, values, sub_map, hidden=()) -> bool:
    if not isinstance(condition, Mapping):
        return False
    cond = condition.get("cond")
    if isinstance(cond, (list, tuple)) and len(cond) > 0:
        return _eval_group(condition.get("rel") or "and", list(cond), values, sub_map, hidden)
    if condition.get("field") and condition.get("operator"):
        return _eval_single(condition["field"], condition["operator"], condition.get("value"),
                            values, sub_map, hidden)
    return False


# ===== 字段状态计算 =====

def _targets_of(rule: Mapping[str, Any]) -> list[str]:
    ids = rule.get("target_field_ids") or []
    if ids:
        return list(ids)
    one = rule.get("target_field_id")
    return [one] if one else []


def compute_field_states(
    fields: list[dict],
    values: Mapping[str, Any] | None,
    rules: list[dict] | None = None,
    permissions: list[dict] | None = None,
) -> FieldStates:
    """算出每个字段的 visible / readonly / required（与前端 computeFieldStates 对等）。

    permissions: [{"fieldId": ..., "access": editable|readonly|hidden|required}]
    """
    values = values or {}
    rules = rules or []
    states: FieldStates = {}
    sub_map = _sub_field_map(fields)

    for f in fields or []:
        props = f.get("props") or {}
        states[f.get("id")] = {
            "visible": props.get("hidden") is not True,
            "readonly": props.get("readonly") is True,
            "required": bool(f.get("required")),
            "masked": False,
        }
        for col in f.get("detail_table_columns") or []:
            cprops = col.get("props") or {}
            states[col.get("id")] = {
                "visible": cprops.get("hidden") is not True,
                "readonly": cprops.get("readonly") is True,
                "required": bool(col.get("required")),
                "masked": False,
            }

    for perm in permissions or []:
        st = states.get(perm.get("fieldId"))
        if not st:
            continue
        access = perm.get("access")
        if access == "hidden":
            st["visible"] = False
        elif access == "masked":
            # 脱敏：字段仍显示，但只给 "***"，且一律不可编辑
            st["masked"] = True
            st["readonly"] = True
        elif access == "readonly":
            st["readonly"] = True
        elif access == "required":
            st["required"] = True
        elif access == "editable":
            st["readonly"] = False

    # 显隐：被隐藏字段的值不再参与其他规则判定，故迭代到不动点（带上限防环）
    vis_rules = [r for r in rules
                 if r.get("type") == "visibility" and (r.get("action") or {}).get("visible") is not None]
    if vis_rules:
        hidden: set[str] = set()
        cap = min(len(vis_rules) + 2, 50)
        for it in range(cap):
            vis: dict[str, bool] = {}
            for rule in vis_rules:
                want = bool((rule.get("action") or {}).get("visible"))
                match = evaluate_condition(rule.get("condition") or {}, values, sub_map, hidden)
                for fid in _targets_of(rule):
                    if fid in states:
                        vis[fid] = want if match else (not want)
            nxt = {fid for fid, v in vis.items() if not v}
            if nxt == hidden or it == cap - 1:
                for fid, v in vis.items():
                    states[fid]["visible"] = v
                break
            hidden = nxt

    for rule in rules:
        if rule.get("type") != "required":
            continue
        want = (rule.get("action") or {}).get("required") is not False
        match = evaluate_condition(rule.get("condition") or {}, values, sub_map)
        for fid in _targets_of(rule):
            if fid in states:
                states[fid]["required"] = want if match else (not want)

    for rule in rules:
        if rule.get("type") != "readonly":
            continue
        want = (rule.get("action") or {}).get("readonly") is not False
        match = evaluate_condition(rule.get("condition") or {}, values, sub_map)
        for fid in _targets_of(rule):
            if fid in states:
                states[fid]["readonly"] = want if match else (not want)

    return states


def validate_required_with_rules(
    fields: list[dict],
    values: Mapping[str, Any] | None,
    rules: list[dict] | None = None,
    permissions: list[dict] | None = None,
) -> str | None:
    """必填校验（跳过被规则隐藏的字段）。通过返回 None，否则返回首个错误文案。

    与前端 FormRenderer.validateRequired 同口径，含明细子表必填列。
    """
    values = values or {}
    states = compute_field_states(fields, values, rules, permissions)
    for f in fields or []:
        if f.get("type") in ("formula", "auto_number"):
            continue
        st = states.get(f.get("id")) or {}
        if st and not st.get("visible", True):
            continue
        if st.get("masked"):
            # 看不到明文就无法填写：脱敏 + 必填会让记录永远存不下去。
            # 与「被隐藏的字段不报必填」是同一条防死锁原则。
            continue
        required = st.get("required") if st else bool(f.get("required"))
        if required and _is_empty(values.get(f.get("id"))):
            return f"「{f.get('label')}」为必填项"
        if f.get("type") == "detail_table":
            rows = values.get(f.get("id"))
            req_cols = [c for c in (f.get("detail_table_columns") or []) if c.get("required")]
            if isinstance(rows, (list, tuple)) and req_cols:
                for i, row in enumerate(rows):
                    for c in req_cols:
                        cell = row.get(c.get("id")) if isinstance(row, Mapping) else None
                        if _is_empty(cell):
                            return f"「{f.get('label')}」第 {i + 1} 行「{c.get('label')}」为必填项"
    return None
