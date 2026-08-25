# -*- coding: utf-8 -*-
"""报价管理：可选关联商机（非必填）；成本价仅内勤/财务/市场技术支持中心/销售经理/管理员可见。"""
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

# 成本价 / 成本价附件：除以下角色外一律不可见（含详情、列表、导出）
QUOTE_COST_SENSITIVE_FIELD_IDS = frozenset({"cost_price", "cost_attachments"})
QUOTE_COST_VISIBLE_ROLES = [
    "lead_intel",       # 信息情报部内勤
    "finance",          # 财务专员
    "finance_manager",  # 财务主管
    "mkt_support",      # 市场技术支持中心
    "sales_manager",    # 销售经理
    "admin",            # 系统管理员
]


def _apply_cost_field_acl(fd: dict[str, Any]) -> None:
    roles = list(QUOTE_COST_VISIBLE_ROLES)
    fd["visible_roles"] = roles
    fd["unmask_roles"] = roles
    if (fd.get("type") or "") in ("file", "image"):
        fd["download_roles"] = roles


def apply_quote_management_fields(field_defs: list[dict[str, Any]]) -> None:
    """确保存在可选「关联商机」；客户类别/价格类型保持审批阶段非必填；成本价 ACL。"""
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
        elif fid in QUOTE_COST_SENSITIVE_FIELD_IDS:
            _apply_cost_field_acl(fd)


def prepare_quote_field_defs(field_defs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """拷贝并注入报价管理运行时字段策略（含成本价 visible_roles）。"""
    defs = [dict(f) if isinstance(f, dict) else f for f in (field_defs or [])]
    apply_quote_management_fields(defs)
    return defs
