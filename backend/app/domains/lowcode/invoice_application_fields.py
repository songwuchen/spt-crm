# -*- coding: utf-8 -*-
"""开票申请：选合同后带出字段（对齐简道云关联查询）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


# 合同明细列 → 开票「合同明细（新增）」列
_LINE_COL_MAP = {
    "name": "product_name",
    "product_name": "product_name",
    "spec": "spec_model",
    "spec_model": "spec_model",
    "unit": "unit",
    "qty": "qty",
    "price": "unit_price",
    "unit_price": "unit_price",
    "amount": "line_amount",
    "line_amount": "line_amount",
}

_DROP_IDS = frozenset({
    "contract_lines_change",
    "product_name_chg",
    "spec_model_chg",
    "unit_chg",
    "qty_chg",
    "unit_price_chg",
    "line_amount_chg",
})

# 选合同后写入的只读字段（清空时一并清）
INVOICE_FILL_CLEAR = [
    "drawing_no",
    "customer_name",
    "dept_contract_no",
    "customer_no",
    "customer_code",
    "sales_person",
    "contract_data",
    "contract_lines_new",
    "total_amount",
    "taxpayer_id",
    "invoice_address_phone",
    "bank_account",
]


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


def map_contract_lines_to_invoice(key_clauses: Any) -> list[dict]:
    out: list[dict] = []
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in _LINE_COL_MAP.items():
            if src in row and row[src] not in (None, "") and dst not in mapped:
                mapped[dst] = row[src]
        qty = _to_number(mapped.get("qty"))
        price = _to_number(mapped.get("unit_price"))
        if qty is not None and price is not None:
            mapped["line_amount"] = round(qty * price, 2)
        if mapped:
            out.append(mapped)
    return out


def build_invoice_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    peer_contract_no: str | None,
    assignee_id: str | None,
    customer_name: str | None,
    customer_code: str | None,
    amount_total: Any = None,  # noqa: ARG001 — 总价由公式计算，保留参数兼容调用方
    taxpayer_id: str | None,
    invoice_address_phone: str | None,
    bank_account: str | None,
    key_clauses_json: Any,
) -> dict[str, Any]:
    lines = map_contract_lines_to_invoice(key_clauses_json)

    return {
        "drawing_no": drawing_no or "",
        "customer_name": customer_name or "",
        "dept_contract_no": peer_contract_no or contract_no or "",
        "customer_no": customer_code or "",
        "customer_code": customer_code or "",
        "sales_person": assignee_id or None,
        "contract_data": contract_no or drawing_no or "",
        "contract_lines_new": lines,
        # total_amount 由公式 SUM(明细.合计) 计算，不在此写入
        "taxpayer_id": taxpayer_id or "",
        "invoice_address_phone": invoice_address_phone or "",
        "bank_account": bank_account or "",
    }


def _invoice_info_fields() -> list[dict]:
    """简道云「开票信息」linkquery → CRM 只读文本字段。"""
    common = {
        "type": "text",
        "required": False,
        "available_on_create": True,
        "fill_stage": "initiator",
        "form_editable": False,
    }
    return [
        {**common, "id": "taxpayer_id", "label": "纳税人识别号",
         "description": "选自合同关联客户，不可编辑。"},
        {**common, "id": "invoice_address_phone", "label": "地址电话",
         "description": "选自合同关联客户，不可编辑。"},
        {**common, "id": "bank_account", "label": "开户行帐号",
         "description": "选自合同关联客户，不可编辑。"},
    ]


def apply_invoice_application_fields(defs: list) -> None:
    """选合同带出 + 删除无用「合同明细（变动）」+ 补开票信息字段。"""
    # 1) 删变动明细
    kept = [f for f in defs if isinstance(f, dict) and f.get("id") not in _DROP_IDS]
    defs[:] = kept

    # 2) 已有 id 集合
    ids = {f.get("id") for f in defs if isinstance(f, dict)}

    # 3) 选择图纸编号 → 合同选择（带出）
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "drawing_no_select":
            f["type"] = "contract"
            f["label"] = "选择合同号"
            f["description"] = "从合同管理选择；选中后带出图纸号、单位、业务员、开票信息与合同明细。"
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = "invoice_application"
            f["props"] = props
            f["required"] = False
            f["available_on_create"] = True
            f["fill_stage"] = "initiator"
        elif fid in (
            "drawing_no", "customer_name", "dept_contract_no", "customer_no",
            "customer_code", "contract_data", "total_amount",
        ):
            f["form_editable"] = False
            f["description"] = (f.get("description") or "") or "由选择合同号自动带出，不可编辑。"
            if fid == "total_amount":
                # 明细带出后用公式汇总，避免手工改总价与明细不一致
                f["type"] = "formula"
                f["props"] = {"formula": "SUM($contract_lines_new.line_amount#)"}
                f["description"] = "由合同明细合计自动汇总。"
            if fid == "contract_data":
                f["label"] = f.get("label") or "合同数据"
                f["description"] = "由选择合同号带出合同编号。"
        elif fid == "contract_lines_new":
            # 选合同只是把明细拷贝进本单 form_data，可增删改；不回写合同原明细
            f["form_editable"] = True
            f["description"] = "选择合同号后自动带出；可在本单增删改行，不影响合同已保存的明细。"
            cols = [dict(c) if isinstance(c, dict) else c for c in (f.get("detail_table_columns") or [])]
            for c in cols:
                if not isinstance(c, dict) or c.get("id") != "line_amount":
                    continue
                c["type"] = "number"
                c["form_editable"] = True
                c["description"] = "默认数量 × 单价，可手改。"
            f["detail_table_columns"] = cols
        elif fid == "sales_person":
            f["form_editable"] = False
            f["description"] = "由选择合同号带出合同业务员，不可编辑。"

    # 4) 插入开票信息字段（紧跟业务员之后）
    missing = [fd for fd in _invoice_info_fields() if fd["id"] not in ids]
    if missing:
        insert_at = next(
            (i + 1 for i, f in enumerate(defs) if isinstance(f, dict) and f.get("id") == "sales_person"),
            None,
        )
        if insert_at is None:
            insert_at = next(
                (i for i, f in enumerate(defs) if isinstance(f, dict) and f.get("id") == "contract_data"),
                len(defs),
            )
        for j, fd in enumerate(missing):
            defs.insert(insert_at + j, fd)
