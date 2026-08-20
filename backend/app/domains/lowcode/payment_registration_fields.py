# -*- coding: utf-8 -*-
"""收款登记字段修正：合计公式 + 单位名称选客户 + 来款日期仅选日。"""
from __future__ import annotations


_OFFICE_FILL_IDS = frozenset({
    "sales_person",
    "payment_allocation",
    "alloc_total",
    "discount_docs",
    "penalty_docs",
    "images",
    "remark_2",
})


def apply_payment_registration_fields(defs: list) -> None:
    """对齐简道云：

    - 单位名称：从客户信息选择
    - 来款日期：只选到日（不选手选时分）
    - 来款合计 / 分配金额合计：明细汇总公式（只读）
    - 内勤填写区：仅审批可填（available_on_create=false）
    """
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "payment_date":
            f["type"] = "date"
            props = dict(f.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            f["props"] = props
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
