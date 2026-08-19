"""人员/部门字段可选范围。

字段 props.pickable_scope 支持：
  { "scope_code": "room_leaders" }
  { "scope_code": "xxx", "filter_by_fields": ["offices", "offices_multi"] }  # 可选按科室收窄
  { "role_codes": ["room_leader"] }   # 兼容旧配置
"""
from __future__ import annotations

# 默认（SPT）租户可使用方案管理预置人选/科室范围；其它租户 ensure 时剥离，避免空范围选不了人
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
SPT_SCHEME_SCOPE_CODES = frozenset({"room_leaders", "scheme_offices", "fa-zxxgy"})
SPT_SCHEME_SCOPED_FIELD_IDS = frozenset({
    "design_assignees", "designer", "transfer_packaging_users",
    "offices", "offices_multi",
})


def strip_spt_scheme_pickable_scopes(
    tenant_id: str | None, field_definitions: list | None,
) -> list:
    """非默认租户：去掉方案管理 SPT 专用 pickable_scope。"""
    defs = list(field_definitions or [])
    if not tenant_id or tenant_id == DEFAULT_TENANT_ID:
        return defs
    out: list = []
    for fd in defs:
        if not isinstance(fd, dict):
            out.append(fd)
            continue
        fid = fd.get("id")
        props = fd.get("props")
        if not isinstance(props, dict):
            out.append(fd)
            continue
        scope = props.get("pickable_scope")
        if not isinstance(scope, dict):
            out.append(fd)
            continue
        code = scope.get("scope_code")
        if fid in SPT_SCHEME_SCOPED_FIELD_IDS or (code and code in SPT_SCHEME_SCOPE_CODES):
            props = {k: v for k, v in props.items() if k != "pickable_scope"}
            fd = dict(fd)
            fd["props"] = props or None
        out.append(fd)
    return out


# 简道云角色 ID → CRM Role.code（生成器仍可用）
JDY_ROLE_TO_CRM_CODE: dict[str, str] = {
    "63815e3a7fb607000acc9195": "room_leader",
}

# 简道云角色 → 预置可选范围 code
JDY_ROLE_TO_SCOPE_CODE: dict[str, str] = {
    "63815e3a7fb607000acc9195": "room_leaders",
    # 客服领图「部门指派-研管办」← 27.3图纸领用申请-研究院安排
    "5f46008a6344180006bfa81a": "dept_dispatch_ygb",
    # 报价管理「冶金装备销售事业部」← 27.7核价管理流程-冶金
    "5f6c394b2ad3770006ded49a": "quote_metallurgy",
}

# 简道云角色名 → 审批人可选范围（charger_rule 用；id 优先）
JDY_ROLE_NAME_TO_APPROVER_SCOPE: dict[str, str] = {
    "27.3图纸领用申请-研究院安排": "dept_dispatch_ygb",
    "27.7核价管理流程-冶金": "quote_metallurgy",
}

# 简道云「一人角色」（角色名即人名/专属岗）→ 指定用户 username（对齐合同等具名审批）
# 勿再降级为 CRM sales_manager（205 上常空成员 → 无审批人自动通过）。
JDY_ROLE_TO_SPECIFIED_USER: dict[str, str] = {
    "5f65673064514d0006b13a66": "01000533004677",  # 王玲玲
    "5f46003a5c11340006b167f2": "02364714147257",  # 热能利用-段荣凯
    "5f69a4d2d4014600062cdd7f": "02364335378133",  # 售前服务通知·总工审批-曹修国
}
JDY_ROLE_NAME_TO_SPECIFIED_USER: dict[str, str] = {
    "王玲玲": "01000533004677",
    "热能利用-段荣凯": "02364714147257",
    "24.2.3合同/项目评审-设计-曹修国": "02364335378133",
    "曹修国": "02364335378133",
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
