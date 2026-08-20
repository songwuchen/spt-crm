"""发货通知：字段运行时补丁（与生成器 / ensure 共用）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

# 选合同后写入的字段（清空合同时一并清）
SHIPMENT_FILL_CLEAR = [
    "consignee_unit",
    "contract_no_text",
    "department",
    "sales_person",
    "dept_contract_no",
    "need_install",
    "counterparty_contract_no",
    "accept_method",
    "accept_docs",
    "contract_amount",
    "ship_lines",
]

# 合同明细列 → 发货明细列（对齐简道云 subLink）
_LINE_COL_MAP = {
    "name": "goods_name",
    "product_name": "goods_name",
    "spec": "spec_model",
    "spec_model": "spec_model",
    "unit": "unit",
    "qty": "qty",
    "amount": "contract_line_amount",
    "line_amount": "contract_line_amount",
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


def map_contract_lines_to_shipment(
    key_clauses: Any,
    *,
    drawing_no: str | None = None,
    contract_no: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    line_contract_no = (drawing_no or "").strip() or (contract_no or "").strip()
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in _LINE_COL_MAP.items():
            if src in row and row[src] not in (None, "") and dst not in mapped:
                val = row[src]
                if dst in ("qty", "contract_line_amount", "line_amount"):
                    mapped[dst] = _to_number(val)
                else:
                    mapped[dst] = val
        qty = _to_number(mapped.get("qty"))
        amount = _to_number(mapped.get("contract_line_amount"))
        if amount is None and qty is not None:
            price = _to_number(row.get("price") or row.get("unit_price"))
            if price is not None:
                amount = round(qty * price, 2)
                mapped["contract_line_amount"] = amount
        if amount is not None:
            mapped["line_amount"] = amount
        if row.get("line_remark") not in (None, ""):
            mapped["line_remark"] = row.get("line_remark")
        if line_contract_no:
            mapped["line_contract_no"] = line_contract_no
        if mapped:
            out.append(mapped)
    return out


def build_shipment_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    peer_contract_no: str | None,
    assignee_id: str | None,
    department_id: str | None,
    customer_name: str | None,
    amount_total: Any = None,
    registration_json: dict | None,
    key_clauses_json: Any = None,
) -> dict[str, Any]:
    """对齐简道云发货通知「合同号选择」linkDataMaps + 发货明细 subLink。"""
    reg = registration_json if isinstance(registration_json, dict) else {}
    lines = map_contract_lines_to_shipment(
        key_clauses_json, drawing_no=drawing_no, contract_no=contract_no,
    )
    return {
        "consignee_unit": customer_name or "",
        "contract_no_text": drawing_no or "",
        "department": department_id or None,
        "sales_person": assignee_id or None,
        "dept_contract_no": contract_no or "",
        "need_install": reg.get("need_install") or "",
        "counterparty_contract_no": peer_contract_no or "",
        "accept_method": reg.get("accept_method") or "",
        "accept_docs": reg.get("accept_materials") or reg.get("accept_docs") or "",
        "contract_amount": _to_number(amount_total),
        "ship_lines": lines,
    }


def apply_shipment_notice_fields(fields: list[dict]) -> None:
    """业务日期只选到日；合同号选择走合同控件并带出关联字段。"""
    for fd in fields:
        if not isinstance(fd, dict):
            continue
        if fd.get("id") in ("biz_datetime", "require_arrive_time"):
            fd["type"] = "date"
            props = dict(fd.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            fd["props"] = props
        if fd.get("id") == "contract_no":
            fd["type"] = "contract"
            fd["label"] = "合同号选择"
            fd["description"] = "从合同管理中选择；选中后带出对方合同号、收货单位、部门、业务员及发货明细。"
            props = dict(fd.get("props") or {})
            props["contract_fill"] = "shipment_notice"
            fd["props"] = props
        if fd.get("id") == "ship_lines":
            fd["description"] = (fd.get("description") or "") or "选择合同号后从合同登记明细自动带出，可在本单增删改。"
