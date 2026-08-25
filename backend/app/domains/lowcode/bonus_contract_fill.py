# -*- coding: utf-8 -*-
"""业务奖金：选合同后字段带出（对齐简道云 combo/linkDataMaps）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

# transfer 合同明细列
_TRANSFER_LINE_COL_MAP = {
    "name": "field",
    "product_name": "field",
    "spec": "field_2",
    "spec_model": "field_2",
    "unit": "field_3",
    "qty": "field_4",
    "price": "field_5",
    "unit_price": "field_5",
    "amount": "field_6",
    "line_amount": "field_6",
}

# 业务发起：子表首列从 field_2 起
_INITIATE_LINE_COL_MAP = {
    "name": "field_2",
    "product_name": "field_2",
    "spec": "field_3",
    "spec_model": "field_3",
    "unit": "field_4",
    "qty": "field_5",
    "price": "field_6",
    "unit_price": "field_6",
    "amount": "field_7",
    "line_amount": "field_7",
}

_BONUS_FILL_READONLY = frozenset({
    "salesperson",
    "sign_date",
    "company_name",
    "contract_lines",
    "contract_amount",
    "payment_method",
})

_COMMISSION_FILL_READONLY = frozenset({
    "company_name",
    "salesperson",
    "department",
    "contract_amount",
})

BONUS_FILL_CLEAR: dict[str, list[str]] = {
    "biz_bonus_transfer": [
        "salesperson", "sign_date", "company_name", "contract_lines",
        "contract_amount", "payment_method",
    ],
    "biz_bonus_biz_initiate": [
        "salesperson", "sign_date", "company_name", "contract_lines",
        "contract_amount", "payment_method",
    ],
    "commission_database": [
        "company_name", "salesperson", "department", "contract_amount",
    ],
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


def map_contract_lines_to_bonus(key_clauses: Any, *, form_key: str) -> list[dict[str, Any]]:
    col_map = (
        _INITIATE_LINE_COL_MAP
        if form_key == "biz_bonus_biz_initiate"
        else _TRANSFER_LINE_COL_MAP
    )
    out: list[dict[str, Any]] = []
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in col_map.items():
            if src in row and row[src] not in (None, "") and dst not in mapped:
                val = row[src]
                if dst in ("field_4", "field_5", "field_6", "field_7") or "field_" in dst:
                    num = _to_number(val)
                    mapped[dst] = num if num is not None else val
                else:
                    mapped[dst] = val
        amount_key = "field_6" if form_key == "biz_bonus_transfer" else "field_7"
        price_key = "field_5" if form_key == "biz_bonus_transfer" else "field_6"
        qty_key = "field_4" if form_key == "biz_bonus_transfer" else "field_5"
        qty = _to_number(mapped.get(qty_key))
        amount = _to_number(mapped.get(amount_key))
        if amount is None and qty is not None:
            price = _to_number(row.get("price") or row.get("unit_price") or mapped.get(price_key))
            if price is not None:
                mapped[amount_key] = round(qty * price, 2)
        if mapped:
            out.append(mapped)
    return out


def _fmt_date(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    return str(raw).strip()[:10]


def _payment_method_text(reg: dict) -> str:
    for key in ("payment_desc", "payment_method", "pay_method", "付款方式"):
        raw = reg.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    forms = reg.get("payment_forms")
    if isinstance(forms, list) and forms:
        return "、".join(str(x).strip() for x in forms if str(x).strip())
    if forms not in (None, ""):
        return str(forms).strip()
    return ""


def _sign_date(reg: dict) -> str:
    for key in ("card_date", "sign_date", "apply_date", "下卡日期"):
        raw = reg.get(key)
        if raw is not None and str(raw).strip():
            return _fmt_date(raw)
    return ""


def _company_name(customer_name: str | None, reg: dict) -> str:
    unit = (customer_name or "").strip()
    if unit:
        return unit
    for key in ("customer_name", "company_name", "单位名称", "客户名称"):
        raw = reg.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def _contract_amount(amount_total: Any, lines: list[dict]) -> float | None:
    if amount_total not in (None, ""):
        n = _to_number(amount_total)
        if n is not None:
            return round(n, 2)
    total = 0.0
    has = False
    amount_keys = ("field_6", "field_7", "line_amount", "amount")
    for row in lines:
        for k in amount_keys:
            n = _to_number(row.get(k))
            if n is not None:
                total += n
                has = True
                break
    return round(total, 2) if has else None


def build_bonus_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    assignee_id: str | None,
    department_id: str | None,
    customer_name: str | None,
    amount_total: Any,
    registration_json: dict | None,
    key_clauses_json: Any,
    form_key: str,
) -> dict[str, Any]:
    """form_key: biz_bonus_transfer | biz_bonus_biz_initiate | commission_database"""
    reg = registration_json if isinstance(registration_json, dict) else {}
    lines = map_contract_lines_to_bonus(key_clauses_json, form_key=form_key)
    company = _company_name(customer_name, reg)
    amount = _contract_amount(amount_total, lines)

    if form_key == "commission_database":
        out: dict[str, Any] = {
            "company_name": company,
            "salesperson": assignee_id or None,
            "department": department_id or None,
            "contract_amount": amount,
        }
        return out

    return {
        "salesperson": assignee_id or None,
        "sign_date": _sign_date(reg),
        "company_name": company,
        "contract_lines": lines,
        "contract_amount": amount,
        "payment_method": _payment_method_text(reg),
    }


def bonus_fill_clear_keys(form_key: str) -> list[str]:
    return list(BONUS_FILL_CLEAR.get(form_key) or BONUS_FILL_CLEAR["biz_bonus_transfer"])


def apply_bonus_contract_fields(defs: list, form_key: str) -> None:
    """图纸编号/合同号 → 合同选择；带出字段只读展示。"""
    contract_field = "drawing_no" if form_key != "commission_database" else "contract_no"
    fill_mode = form_key

    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == contract_field:
            f["type"] = "contract"
            f["label"] = "图纸编号" if fid == "drawing_no" else "合同号"
            f["description"] = (
                "从合同管理选择（对齐简道云图纸编号）；"
                "选中后自动带出业务员、签订日期、单位名称、合同明细等。"
                if fid == "drawing_no"
                else "从合同管理选择；选中后自动带出单位、业务员、部门与合同金额。"
            )
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = fill_mode
            f["props"] = props
            f["available_on_create"] = True
            f["fill_stage"] = "initiator"
        elif fid == "department" and form_key in ("biz_bonus_transfer", "biz_bonus_biz_initiate"):
            props = dict(f.get("props") or {})
            props.setdefault("default_current_dept", True)
            f["props"] = props
        elif fid in _BONUS_FILL_READONLY and form_key != "commission_database":
            f["form_editable"] = False
            f["available_on_create"] = True
            f["fill_stage"] = "initiator"
            f["description"] = f.get("description") or "由所选合同自动带出，不可手改。"
        elif fid in _COMMISSION_FILL_READONLY and form_key == "commission_database":
            if fid != "contract_no":
                f["form_editable"] = False
                f["available_on_create"] = True
                f["fill_stage"] = "initiator"
                f["description"] = f.get("description") or "由所选合同自动带出，不可手改。"
