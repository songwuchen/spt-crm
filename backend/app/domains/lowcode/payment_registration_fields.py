# -*- coding: utf-8 -*-
"""收款登记字段修正：合计公式 + 单位名称选客户 + 来款日期仅选日 + 收款号流水。"""
from __future__ import annotations

from typing import Any


_OFFICE_FILL_IDS = frozenset({
    "sales_person",
    "payment_allocation",
    "alloc_total",
    "discount_docs",
    "penalty_docs",
    "images",
    "remark_2",
})

# 收款号：固定前缀 SKDJ- + 5 位递增（不自动重置），对齐开票 KPSQ- 风格
PAYMENT_SERIAL_PREFIX = "SKDJ-"
PAYMENT_SERIAL_NO_RULES: list[dict[str, Any]] = [
    {"type": "text", "value": PAYMENT_SERIAL_PREFIX},
    {
        "type": "counter",
        "digits": 5,
        "fixed": True,
        "reset_period": "none",
        "initial_value": 1,
    },
]


def _apply_date_only(field: dict) -> None:
    """对齐简道云：日期字段只选到日，不选时分。"""
    props = dict(field.get("props") or {})
    props["show_time"] = False
    props["date_only"] = True
    field["type"] = "date"
    field["props"] = props


def apply_payment_registration_fields(defs: list) -> None:
    """对齐简道云：

    - 收款号：系统流水号（auto_number）
    - 单位名称：从客户信息选择
    - 来款日期 / 来款明细「到期日」：只选到日（不选时分）
    - 来款合计 / 分配金额合计：明细汇总公式（只读）
    - 内勤填写区：仅审批可填（available_on_create=false）
    """
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "payment_no":
            f["type"] = "auto_number"
            f["label"] = f.get("label") or "收款号"
            f["form_editable"] = False
            f["available_on_create"] = True
            f["fill_stage"] = "initiator"
            f["required"] = False
            props = dict(f.get("props") or {})
            props["serial_rules"] = [dict(r) for r in PAYMENT_SERIAL_NO_RULES]
            f["props"] = props
            f["description"] = (
                f"系统收款号：{PAYMENT_SERIAL_PREFIX} + 5 位递增序号（不自动重置）。"
            )
        elif fid == "payment_date":
            _apply_date_only(f)
        elif fid == "payment_details":
            for col in f.get("detail_table_columns") or []:
                if isinstance(col, dict) and col.get("id") == "due_date":
                    _apply_date_only(col)
                    col["label"] = col.get("label") or "到期日"
        elif fid == "customer_name":
            f["type"] = "customer"
            f["label"] = f.get("label") or "单位名称"
            f["description"] = "从客户信息中选择。"
        elif fid == "payment_total":
            f["type"] = "formula"
            f["label"] = f.get("label") or "来款合计"
            f["required"] = False
            f["available_on_create"] = True
            f["fill_stage"] = "initiator"
            f["description"] = "由来款明细金额自动汇总，不可编辑。"
            f["props"] = {"formula": "SUM($payment_details.amount#)"}
        elif fid == "alloc_total":
            f["type"] = "formula"
            f["label"] = f.get("label") or "分配金额合计"
            f["required"] = False
            f["available_on_create"] = False
            f["fill_stage"] = "approver"
            f["description"] = "由款项分配金额自动汇总；内勤审批时计算。"
            f["props"] = {"formula": "SUM($payment_allocation.alloc_amount#)"}
        elif fid in _OFFICE_FILL_IDS:
            f["available_on_create"] = False
            f["fill_stage"] = "approver"
            if fid != "alloc_total":
                f["required"] = False
