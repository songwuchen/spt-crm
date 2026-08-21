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
    # 客户名：主数据优先；否则合同登记里的单位/客户名称
    unit = (customer_name or "").strip()
    if not unit:
        for key in ("customer_name", "company_name", "单位名称", "客户名称"):
            raw = reg.get(key)
            if raw is not None and str(raw).strip():
                unit = str(raw).strip()
                break

    if mode == "contract_no_select":
        return {
            "yes_contract_no": contract_no or "",
            "yes_sales_person": sales,
            "yes_customer_name": unit,
            "contract_tech_review_sn": reg.get("review_sn") or "",
        }

    # drawing_no_query（非补充）：图纸/明细等 + 单位名称（表单上（是）单位名称也会展示）
    return {
        "no_drawing_no": drawing_no or "",
        "no_sales_person": sales,
        "yes_customer_name": unit,
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
        "no_drawing_no", "no_sales_person", "yes_customer_name", "prod_card_line_items",
        "tech_params", "packaging_req", "remark_prod_card", "paint_req",
        "special_reminder", "no_warranty_period", "project_name",
        "contract_tech_review_sn",
    ]


# 简道云 sn：固定「1.2.8」+ 5 位递增、不重置（生成器曾把 sn 放进 SKIP_TYPES）
PROD_CARD_SERIAL_PREFIX = "1.2.8"
PROD_CARD_SERIAL_NO_RULES: list[dict[str, Any]] = [
    {"type": "text", "value": PROD_CARD_SERIAL_PREFIX},
    {
        "type": "counter",
        "digits": 5,
        "fixed": True,
        "reset_period": "none",
        "initial_value": 1,
    },
]


def ensure_prod_card_serial_no_field(defs: list) -> None:
    """确保生产卡有流程编号 auto_number；无则插到字段列表最前。"""
    serial = None
    for f in defs:
        if isinstance(f, dict) and f.get("id") == "serial_no":
            serial = f
            break
    if serial is None:
        serial = {
            "id": "serial_no",
            "type": "auto_number",
            "label": "流程编号",
            "jdy_widget": "_widget_1617693684982",
        }
        defs.insert(0, serial)
    serial["type"] = "auto_number"
    serial["label"] = serial.get("label") or "流程编号"
    serial["form_editable"] = False
    serial["available_on_create"] = True
    serial["fill_stage"] = "initiator"
    serial["required"] = False
    props = dict(serial.get("props") or {})
    props["serial_rules"] = [dict(r) for r in PROD_CARD_SERIAL_NO_RULES]
    serial["props"] = props
    serial["description"] = (
        f"系统流水号：{PROD_CARD_SERIAL_PREFIX} + 5 位递增序号（不自动重置）。"
    )
    if not serial.get("jdy_widget"):
        serial["jdy_widget"] = "_widget_1617693684982"


def apply_prod_card_contract_pick_fields(defs: list) -> None:
    """把图纸编号查询/合同号选择改为 contract 类型，并挂部门过滤 + 带出模式。

    同时默认「是否为补充」=否：显隐规则在未选时会把两个选合同字段都藏掉，
    新建打开时必须能立刻看到合同下拉。
    提交人 / 所在部门默认当前用户与当前部门。
    「确认协议 / 设计指派填写」仅审批节点可见（对齐简道云，不在发起页展示）。
    补齐流程编号（简道云 sn：1.2.8 + 五位不重置；生成器曾跳过 sn 类型）。
    """
    ensure_prod_card_serial_no_field(defs)
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "is_supplement":
            # 未选时两边合同字段均隐藏；默认否 → 显示「图纸编号查询」合同选择
            f["default_value"] = "否"
        elif fid == "submitter":
            props = dict(f.get("props") or {})
            props["default_current_user"] = True
            f["props"] = props
        elif fid == "department":
            props = dict(f.get("props") or {})
            props["default_current_dept"] = True
            f["props"] = props
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
            f["description"] = "从合同管理选择；按所在部门过滤；选中后带出合同号/单位名称/业务员。"
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = "contract_no_select"
            f["props"] = props
        elif fid == "yes_customer_name":
            # 与「(否)图纸编号」同排：用普通输入框展示（选合同自动带出），勿 props.readonly（会变纯文本）
            props = dict(f.get("props") or {})
            props.pop("readonly", None)
            f["props"] = props or None
            f["description"] = f.get("description") or "由所选合同自动带出单位名称。"
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

    apply_prod_card_approver_only_fields(defs)


# 圈选区：确认协议 + 设计指派填写（安装图项目号 / 室主任0414 等）——发起页不展示
_PROD_CARD_APPROVER_ONLY: dict[str, str] = {
    "confirm_agreement": "required",
    "install_project_no": "editable",
    "f_0414": "required",
    "has_install_project": "required",
    "design_assignees": "required",
}


def apply_prod_card_approver_only_fields(defs: list) -> None:
    """确认协议 / 设计指派填写：仅审批可填，创建页隐藏；字段级必填下沉到节点 perms。"""
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid not in _PROD_CARD_APPROVER_ONLY:
            continue
        f["available_on_create"] = False
        f["fill_stage"] = "approver"
        # 发起不再校验；审批节点 field_perms 再要求
        f["required"] = False


def apply_prod_card_design_assign_field_perms(nodes: list | None) -> bool:
    """研管办安排节点补上确认协议 / 安装图项目号 / 室主任0414 等可写权限。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        name = str(n.get("name") or "")
        if "研管办安排" not in name:
            continue
        perms = list(n.get("field_perms") or [])
        by_field = {
            str(p.get("field")): p
            for p in perms
            if isinstance(p, dict) and p.get("field")
        }
        node_changed = False
        for fid, access in _PROD_CARD_APPROVER_ONLY.items():
            cur = by_field.get(fid)
            if not cur:
                perms.append({"field": fid, "access": access})
                node_changed = True
            elif access == "required" and cur.get("access") != "required":
                cur["access"] = "required"
                node_changed = True
        if node_changed:
            n["field_perms"] = perms
            changed = True
    return changed


def build_prod_card_fill_from_tar(*, review_code: str | None) -> dict[str, Any]:
    """生产卡选技术协议评审后的带出（对齐简道云 linkDataMaps：仅流水号）。"""
    return {"contract_tech_review_sn": (review_code or "").strip()}


def prod_card_tar_fill_clear_keys() -> list[str]:
    return ["contract_tech_review_sn"]


# 「生产卡通知单上的内容」：仅「是否为补充=否」时展示（补充单不填生产卡正文）
_PROD_CARD_NOTICE_FIELDS: tuple[str, ...] = (
    "prod_card_line_items",
    "packaging_req",
    "project_name",
    "paint_req",
    "tech_params",
    "no_warranty_period",
    "special_reminder",
    "remark_prod_card",
    "special_reminder_multi",
)
_PROD_CARD_NOTICE_RULE_IDS = frozenset(
    f"crm_vis_prod_notice_{fid}" for fid in _PROD_CARD_NOTICE_FIELDS
)
_PROD_CARD_NOTICE_WHEN_NOT_SUPPLEMENT = {
    "field": "is_supplement",
    "operator": "in",
    "value": ["否"],
}


def apply_prod_card_supplement_rules(rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """合并「是否为补充=否 → 显示生产卡通知单内容」显隐规则。"""
    out: list[dict[str, Any]] = [
        r for r in (rules or [])
        if isinstance(r, dict) and r.get("id") not in _PROD_CARD_NOTICE_RULE_IDS
    ]
    for fid in _PROD_CARD_NOTICE_FIELDS:
        out.append({
            "id": f"crm_vis_prod_notice_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(_PROD_CARD_NOTICE_WHEN_NOT_SUPPLEMENT),
            "action": {"visible": True},
            "enabled": True,
        })
    return out
