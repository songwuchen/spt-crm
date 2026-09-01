# -*- coding: utf-8 -*-
"""合同及发货借据：选合同带出 + 内置字段运行时补丁。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

# 选 field_5「选择合同信息」后写入；清空时一并清
LOAN_FILL_CLEAR = [
    "customer_name",
    "contract_no",
    "sales_person",
    "field_6",
    "field_2",
    "field_7",
    "field_13",
]

_LINE_COL_MAP = {
    "name": "field_8",
    "product_name": "field_8",
    "spec": "field_9",
    "spec_model": "field_9",
    "qty": "field_10",
    "unit": "field_11",
    "price": "n",
    "unit_price": "n",
    "amount": "field_12",
    "line_amount": "field_12",
}


def _as_rows(key_clauses: Any) -> list[dict]:
    if isinstance(key_clauses, list):
        return [r for r in key_clauses if isinstance(r, dict)]
    if isinstance(key_clauses, dict):
        for k in ("rows", "items", "line_items", "data"):
            v = key_clauses.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
        vals = list(key_clauses.values())
        if vals and all(isinstance(x, dict) for x in vals):
            return [x for x in vals if isinstance(x, dict)]
    return []


def _to_number(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def map_contract_lines_to_loan_detail(key_clauses: Any) -> list[dict]:
    """合同登记明细 → 借据「明细」子表（对齐简道云 linkDataMaps）。"""
    out: list[dict] = []
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in _LINE_COL_MAP.items():
            if src in row and row[src] not in (None, "") and dst not in mapped:
                mapped[dst] = row[src]
        qty = _to_number(mapped.get("field_10"))
        price = _to_number(mapped.get("n"))
        if qty is not None and price is not None and mapped.get("field_12") in (None, ""):
            mapped["field_12"] = round(qty * price, 2)
        if mapped:
            out.append(mapped)
    return out


def _sum_line_totals(lines: list[dict[str, Any]]) -> float | None:
    total = 0.0
    has = False
    for row in lines:
        amt = _to_number(row.get("field_12"))
        if amt is None:
            continue
        total += amt
        has = True
    return round(total, 2) if has else None


def _order_date_from_registration(registration_json: dict | None) -> str | None:
    reg = registration_json if isinstance(registration_json, dict) else {}
    for key in ("order_date", "sign_date", "订货日期", "签订日期"):
        raw = reg.get(key)
        if raw not in (None, ""):
            return str(raw)
    return None


def build_loan_fill_from_contract(
    *,
    contract_id: str,
    contract_no: str | None,
    drawing_no: str | None,
    assignee_id: str | None,
    department_id: str | None,
    customer_id: str | None,
    key_clauses_json: Any,
    registration_json: dict | None = None,
) -> dict[str, Any]:
    """对齐简道云「选择合同信息」linkDataMaps：客户/图纸/部门/业务员/明细/订货日期。"""
    lines = map_contract_lines_to_loan_detail(key_clauses_json)
    total = _sum_line_totals(lines)
    order_date = _order_date_from_registration(registration_json)
    fill: dict[str, Any] = {
        "customer_name": customer_id or None,
        "contract_no": contract_id,
        "sales_person": assignee_id or None,
        "field_6": department_id or None,
        "field_7": lines,
    }
    if order_date:
        fill["field_2"] = order_date
    if total is not None:
        fill["field_13"] = total
    if drawing_no and not contract_no:
        pass  # contract_no 字段存 CRM 合同 id，展示走 ContractField 回显
    return fill


def apply_contract_shipment_loan_fields(fields: list[dict]) -> None:
    """ensure_builtin / 生成器共用：合同选择器 + 带出说明。"""
    for fd in fields:
        if not isinstance(fd, dict):
            continue
        wid = fd.get("jdy_widget")
        fid = fd.get("id")
        if wid == "_widget_1756342534747" or fid == "field_5":
            fd["type"] = "contract"
            fd["label"] = "选择合同信息"
            fd["description"] = "从合同管理中选择；选中后带出客户、图纸编号、业务部门、业务员及明细。"
            props = dict(fd.get("props") or {})
            props["contract_fill"] = "contract_shipment_loan"
            fd["props"] = props
        if fid == "contract_no":
            fd["type"] = "contract"
            fd["label"] = fd.get("label") or "图纸编号"
            fd["form_editable"] = False
            fd["description"] = "选择合同信息后自动带出（按图纸编号展示）。"
        if fid == "field_7":
            fd["description"] = (fd.get("description") or "") or "选择合同后从合同登记明细自动带出，可增删改。"
            for col in fd.get("detail_table_columns") or []:
                if not isinstance(col, dict) or col.get("id") != "field_12":
                    continue
                props = dict(col.get("props") or {})
                props["formula"] = "$field_10#*$n#"
                col["props"] = props
        if fid == "field_13":
            # 对齐简道云：SUM(明细.总价*（元）)
            fd["type"] = "formula"
            fd["label"] = fd.get("label") or "借据总金额*"
            fd["required"] = False
            fd["form_editable"] = False
            fd["description"] = "由明细「总价*（元）」自动汇总，不可编辑。"
            fd["props"] = {"formula": "SUM($field_7.field_12#)"}
