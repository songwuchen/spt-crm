# -*- coding: utf-8 -*-
"""生产卡选合同后的字段带出（对齐简道云 linkDataMaps）。"""
from __future__ import annotations

from typing import Any


# 合同明细列 → 生产卡明细列
_LINE_COL_MAP = {
    "product_type": "product_type_2",
    "name": "product_name_3",
    "spec": "spec_model_3",
    "unit": "unit_3",
    "qty": "qty_3",
    "elec_ctrl": "electric_control",
    "standard": "tech_params_line",
    "line_remark": "field_3",
}


def _as_rows(key_clauses: Any) -> list[dict]:
    if isinstance(key_clauses, list):
        return [r for r in key_clauses if isinstance(r, dict)]
    if isinstance(key_clauses, dict):
        for k in ("rows", "items", "line_items", "data"):
            v = key_clauses.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
        # 有时整表就是 {0: {...}, 1: {...}}
        vals = list(key_clauses.values())
        if vals and all(isinstance(x, dict) for x in vals):
            return [x for x in vals if isinstance(x, dict)]
    return []


def map_contract_lines_to_prod_card(key_clauses: Any) -> list[dict]:
    out: list[dict] = []
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in _LINE_COL_MAP.items():
            if src in row and row[src] not in (None, ""):
                mapped[dst] = row[src]
        if mapped:
            out.append(mapped)
    return out


def build_prod_card_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    assignee_id: str | None,
    assignee_name: str | None,
    customer_name: str | None,
    registration_json: dict | None,
    key_clauses_json: Any,
    mode: str,
) -> dict[str, Any]:
    """mode: drawing_no_query | contract_no_select"""
    reg = registration_json if isinstance(registration_json, dict) else {}
    lines = map_contract_lines_to_prod_card(key_clauses_json)
    sales = assignee_id or None

    if mode == "contract_no_select":
        return {
            "yes_contract_no": contract_no or "",
            "yes_sales_person": sales,
            "yes_customer_name": customer_name or "",
            "contract_tech_review_sn": reg.get("review_sn") or "",
        }

    # drawing_no_query（非补充）
    return {
        "no_drawing_no": drawing_no or "",
        "no_sales_person": sales,
        "prod_card_line_items": lines,
        "tech_params": reg.get("tech_requirements") or "",
        "packaging_req": reg.get("packaging") or "",
        "remark_prod_card": reg.get("remark") or "",
        "paint_req": reg.get("paint_req") or "",
        "special_reminder": reg.get("special_note") or "",
        "no_warranty_period": reg.get("warranty_period") or "",
        "project_name": reg.get("project_name") or "",
        "contract_tech_review_sn": reg.get("review_sn") or "",
    }


def prod_card_fill_clear_keys(mode: str) -> list[str]:
    if mode == "contract_no_select":
        return ["yes_contract_no", "yes_sales_person", "yes_customer_name", "contract_tech_review_sn"]
    return [
        "no_drawing_no", "no_sales_person", "prod_card_line_items",
        "tech_params", "packaging_req", "remark_prod_card", "paint_req",
        "special_reminder", "no_warranty_period", "project_name",
        "contract_tech_review_sn",
    ]


def apply_prod_card_contract_pick_fields(defs: list) -> None:
    """把图纸编号查询/合同号选择改为 contract 类型，并挂部门过滤 + 带出模式。

    同时默认「是否为补充」=否：显隐规则在未选时会把两个选合同字段都藏掉，
    新建打开时必须能立刻看到合同下拉。
    """
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "is_supplement":
            # 未选时两边合同字段均隐藏；默认否 → 显示「图纸编号查询」合同选择
            f["default_value"] = "否"
        elif fid == "drawing_no_query":
            f["type"] = "contract"
            f["label"] = "选择合同（图纸编号查询）"
            f["description"] = "从合同管理选择；按所在部门过滤；选中后带出图纸号/明细等。"
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = "drawing_no_query"
            f["props"] = props
        elif fid == "contract_no_select":
            f["type"] = "contract"
            f["label"] = "选择合同（合同号）"
            f["description"] = "从合同管理选择；按所在部门过滤；选中后带出合同号/客户/业务员。"
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = "contract_no_select"
            f["props"] = props
        elif fid == "select_contract_tech_review":
            # 简道云 linkfield → 技术协议评审；选中后带出流水号（linkDataMaps）
            f["type"] = "tech_agreement_review"
            f["label"] = "选择合同技术协议评审"
            f["description"] = (
                "从技术协议评审中选择（申请人=提交人或业务部门=所在部门）；"
                "选中后自动带出流水号。"
            )
            props = dict(f.get("props") or {})
            props["filter_by_submitter_field"] = "submitter"
            props["filter_by_department_field"] = "department"
            props["tar_fill"] = "prod_card_sn"
            f["props"] = props
        elif fid == "contract_tech_review_sn":
            props = dict(f.get("props") or {})
            props["readonly"] = True
            f["props"] = props
            f["description"] = f.get("description") or "由所选技术协议评审自动带出，不可手改。"


def build_prod_card_fill_from_tar(*, review_code: str | None) -> dict[str, Any]:
    """生产卡选技术协议评审后的带出（对齐简道云 linkDataMaps：仅流水号）。"""
    return {"contract_tech_review_sn": (review_code or "").strip()}


def prod_card_tar_fill_clear_keys() -> list[str]:
    return ["contract_tech_review_sn"]
