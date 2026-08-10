"""人员/部门字段可选范围。

字段 props.pickable_scope 支持：
  { "scope_code": "room_leaders" }
  { "scope_code": "xxx", "filter_by_fields": ["offices", "offices_multi"] }  # 可选按科室收窄
  { "role_codes": ["room_leader"] }   # 兼容旧配置
"""
from __future__ import annotations

# 简道云角色 ID → CRM Role.code（生成器仍可用）
JDY_ROLE_TO_CRM_CODE: dict[str, str] = {
    "63815e3a7fb607000acc9195": "room_leader",
}

# 简道云角色 → 预置可选范围 code
JDY_ROLE_TO_SCOPE_CODE: dict[str, str] = {
    "63815e3a7fb607000acc9195": "room_leaders",
}

# 简道云部门 limit.departs → 预置可选范围（核价管理「采购」= 计划采购部）
JDY_DEPT_TO_SCOPE_CODE: dict[str, str] = {
    "56ca5b8af97e80434fc06129": "quote_purchasers",
}


def pickable_scope_from_jdy_limit(limit: dict | None) -> dict | None:
    """从 JDY widget.limit 生成 props.pickable_scope（优先 scope_code）。"""
    if not isinstance(limit, dict):
        return None
    role_ids = limit.get("roles") or []
    scope_codes: list[str] = []
    role_codes: list[str] = []
    for rid in role_ids:
        sc = JDY_ROLE_TO_SCOPE_CODE.get(str(rid))
        if sc and sc not in scope_codes:
            scope_codes.append(sc)
        code = JDY_ROLE_TO_CRM_CODE.get(str(rid))
        if code and code not in role_codes:
            role_codes.append(code)
    if scope_codes:
        # 方案管理：设计指派/设计人按 room_leaders 范围选人，不再按科室字段二次收窄
        return {"scope_code": scope_codes[0]}
    if role_codes:
        return {"role_codes": role_codes}
    for did in limit.get("departs") or []:
        sc = JDY_DEPT_TO_SCOPE_CODE.get(str(did))
        if sc:
            return {"scope_code": sc}
    return None


def scope_props_from_field(fd: dict | None) -> dict:
    if not isinstance(fd, dict):
        return {}
    props = fd.get("props") if isinstance(fd.get("props"), dict) else {}
    scope = props.get("pickable_scope") if isinstance(props.get("pickable_scope"), dict) else {}
    return scope if isinstance(scope, dict) else {}


def role_codes_from_field(fd: dict | None) -> list[str]:
    """兼容：仅 role_codes（无 scope_code 时）。有 scope_code 时由引擎走范围表。"""
    scope = scope_props_from_field(fd)
    if scope.get("scope_code"):
        return []
    codes = scope.get("role_codes") or []
    return [str(c) for c in codes if c]


def scope_code_from_field(fd: dict | None) -> str | None:
    code = scope_props_from_field(fd).get("scope_code")
    return str(code) if code else None


def filter_by_fields_from_field(fd: dict | None) -> list[str]:
    scope = scope_props_from_field(fd)
    raw = scope.get("filter_by_fields") or []
    return [str(x) for x in raw if x]
