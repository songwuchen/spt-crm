# -*- coding: utf-8 -*-
"""客服领图字段后处理：指派节点人选范围 / 下单日期 / 设计单分派联动。"""
from __future__ import annotations

from typing import Any

from app.domains.lowcode.pickable_scope import apply_scheme_design_person_scope_rules

# 与合同图纸领用「研究院安排」一致的指派字段可选范围
_ASSIGN_SCOPES: dict[str, dict[str, Any]] = {
    "transfer_packaging_users": {"scope_code": "fa-zxxgy"},
    "design_assignees": {"scope_code": "room_leaders"},
    "offices": {"scope_code": "scheme_offices"},
}

# 简道云 field_show_rules（_jdy_customer_service_linkages.json）：
# 总部单/共同 → 设计指派；新乡单/郑州单/共同/包装单 → 转新乡、工艺包装
CS_DRAWING_DISPATCH_RULES: list[dict[str, Any]] = [
    {
        "id": "jdy_vis_design_assignees",
        "type": "visibility",
        "target_field_id": "design_assignees",
        "condition": {
            "field": "design_dispatch",
            "operator": "in",
            "value": ["总部单", "共同"],
        },
        "action": {"visible": True},
    },
    {
        "id": "jdy_req_design_assignees",
        "type": "required",
        "target_field_id": "design_assignees",
        "condition": {
            "field": "design_dispatch",
            "operator": "in",
            "value": ["总部单", "共同"],
        },
        "action": {"required": True},
    },
    {
        "id": "jdy_vis_transfer_packaging_users",
        "type": "visibility",
        "target_field_id": "transfer_packaging_users",
        "condition": {
            "field": "design_dispatch",
            "operator": "in",
            "value": ["新乡单", "郑州单", "共同", "包装单"],
        },
        "action": {"visible": True},
    },
    {
        "id": "jdy_req_transfer_packaging_users",
        "type": "required",
        "target_field_id": "transfer_packaging_users",
        "condition": {
            "field": "design_dispatch",
            "operator": "in",
            "value": ["新乡单", "郑州单", "共同", "包装单"],
        },
        "action": {"required": True},
    },
]

_DISPATCH_RULE_IDS = {r["id"] for r in CS_DRAWING_DISPATCH_RULES}


def apply_cs_drawing_request_fields(field_defs: list[dict[str, Any]]) -> None:
    """就地修正 cs_drawing_request：可选范围 + 下单日期（仅日期、审批节点当天）。"""
    for fd in field_defs or []:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        if not fid:
            continue

        if fid in _ASSIGN_SCOPES:
            props = dict(fd.get("props") or {})
            props["pickable_scope"] = dict(_ASSIGN_SCOPES[fid])
            fd["props"] = props
            if fid == "transfer_packaging_users":
                fd["type"] = "person_multi"
            elif fid == "design_assignees":
                fd["type"] = "person_multi"
            elif fid == "offices":
                # 简道云为多选科室；范围与图纸领用 scheme_offices 一致
                fd["type"] = "department_multi"
                fd["label"] = fd.get("label") or "科室"

        elif fid == "order_date":
            # 对齐图纸领用 / 安装图：只选日期，打开指派节点时默认当天
            fd["type"] = "date"
            fd["label"] = "下单日期"
            props = dict(fd.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            props.pop("default_today", None)
            props["default_today_on_approve"] = True
            fd["props"] = props

        elif fid == "designer":
            # 设计人全员可选（与图纸领用一致）
            props = dict(fd.get("props") or {})
            if "pickable_scope" in props:
                props.pop("pickable_scope")
                fd["props"] = props or None

    apply_scheme_design_person_scope_rules(field_defs)


def apply_cs_drawing_request_rules(rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """合并设计单分派显隐/条件必填；替换同 id 旧规则，保留其它规则。"""
    out: list[dict[str, Any]] = [
        r for r in (rules or [])
        if isinstance(r, dict) and r.get("id") not in _DISPATCH_RULE_IDS
    ]
    out.extend(dict(r) for r in CS_DRAWING_DISPATCH_RULES)
    return out
