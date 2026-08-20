# -*- coding: utf-8 -*-
"""客服领图字段后处理：指派节点人选范围 / 下单日期对齐图纸领用·安装图。"""
from __future__ import annotations

from typing import Any

from app.domains.lowcode.pickable_scope import apply_scheme_design_person_scope_rules

# 与合同图纸领用「研究院安排」一致的指派字段可选范围
_ASSIGN_SCOPES: dict[str, dict[str, Any]] = {
    "transfer_packaging_users": {"scope_code": "fa-zxxgy"},
    "design_assignees": {"scope_code": "room_leaders"},
    "offices": {"scope_code": "scheme_offices"},
}


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
