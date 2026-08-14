# -*- coding: utf-8 -*-
"""报价管理：可选关联商机（非必填）。"""
from __future__ import annotations

from typing import Any

_RELATED_PROJECT = {
    "id": "related_project",
    "type": "project",
    "label": "关联商机",
    "required": False,
    "description": "从商机管理中选择；可不选，仅填客户名称。选中后可回填客户。",
    "available_on_create": True,
    "fill_stage": "initiator",
}


def apply_quote_management_fields(field_defs: list[dict[str, Any]]) -> None:
    """确保存在可选「关联商机」；客户类别/价格类型保持审批阶段非必填。"""
    if not isinstance(field_defs, list):
        return

    has_project = any(
        isinstance(fd, dict) and fd.get("id") == "related_project" for fd in field_defs
    )
    if not has_project:
        # 插在客户名称前，便于先选商机再回填客户
        insert_at = next(
            (i for i, fd in enumerate(field_defs)
             if isinstance(fd, dict) and fd.get("id") == "customer_name"),
            len(field_defs),
        )
        field_defs.insert(insert_at, dict(_RELATED_PROJECT))

    for fd in field_defs:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        if fid == "related_project":
            fd["type"] = "project"
            fd["label"] = fd.get("label") or "关联商机"
            fd["required"] = False
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            if not fd.get("description"):
                fd["description"] = _RELATED_PROJECT["description"]
        elif fid in ("customer_category", "price_type"):
            fd["required"] = False
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
