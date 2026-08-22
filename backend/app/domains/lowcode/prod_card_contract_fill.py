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


def _fmt_delivery_date(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    return str(raw).strip()[:10]


def build_prod_card_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    assignee_id: str | None,
    assignee_name: str | None,
    customer_name: str | None,
    delivery_date: str | None = None,
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
    delivery = _fmt_delivery_date(delivery_date) or _fmt_delivery_date(reg.get("delivery_date"))
    has_intel = str(reg.get("has_intelligence") or reg.get("has_smart") or "").strip()
    is_export = str(reg.get("is_export") or "").strip()

    if mode == "contract_no_select":
        # 简道云「合同号选择1」linkDataMaps：仅合同号 / 业务员 / 单位名称 / 评审流水号
        return {
            "yes_contract_no": contract_no or "",
            "yes_sales_person": sales,
            "yes_customer_name": unit,
            "contract_tech_review_sn": reg.get("review_sn") or "",
        }

    # drawing_no_query（非补充）：对齐简道云 linkfield 同区展示的关键信息
    return {
        "no_drawing_no": drawing_no or "",
        "no_sales_person": sales,
        "yes_customer_name": unit,
        "contract_delivery_date": delivery,
        "prod_card_line_items": lines,
        "tech_params": reg.get("tech_requirements") or "",
        "packaging_req": reg.get("packaging") or "",
        "remark_prod_card": reg.get("remark") or "",
        "paint_req": reg.get("paint_req") or "",
        "special_reminder": reg.get("special_note") or "",
        "no_warranty_period": reg.get("warranty_period") or "",
        "project_name": reg.get("project_name") or "",
        "has_intelligence": has_intel,
        "is_export_equipment": is_export,
        "contract_tech_review_sn": reg.get("review_sn") or "",
    }


def prod_card_fill_clear_keys(mode: str) -> list[str]:
    if mode == "contract_no_select":
        return [
            "yes_contract_no", "yes_sales_person", "yes_customer_name", "contract_tech_review_sn",
            "region_manager",
        ]
    return [
        "no_drawing_no", "no_sales_person", "yes_customer_name", "prod_card_line_items",
        "tech_params", "packaging_req", "remark_prod_card", "paint_req",
        "special_reminder", "no_warranty_period", "project_name",
        "contract_delivery_date", "has_intelligence", "is_export_equipment",
        "contract_tech_review_sn", "region_manager",
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


# 选合同后自动带出、发起页不可手改的字段
_CONTRACT_PICK_READONLY_IDS = frozenset({
    "no_sales_person",
    "yes_sales_person",
    "no_drawing_no",
    "yes_contract_no",
    "yes_customer_name",
    "region_manager",
    "tech_params",
    "packaging_req",
    "remark_prod_card",
    "paint_req",
    "special_reminder",
    "no_warranty_period",
    "project_name",
    "prod_card_line_items",
    "contract_delivery_date",
    "has_intelligence",
    "is_export_equipment",
})

# 简道云 linkDataMaps：否=图纸编号查询（整块合同信息）；是=合同号选择（仅 4 项）
_PC_DRAWING_ONLY_FILL_FIELDS: tuple[str, ...] = (
    "no_drawing_no",
    "no_sales_person",
    "contract_delivery_date",
    "project_name",
    "packaging_req",
    "prod_card_line_items",
    "paint_req",
    "has_intelligence",
    "is_export_equipment",
    "no_warranty_period",
    "special_reminder",
    "tech_params",
    "remark_prod_card",
)
_PC_YES_ONLY_FILL_FIELDS: tuple[str, ...] = (
    "yes_contract_no",
    "yes_sales_person",
)
_PC_SHARED_CONTRACT_FILL_FIELDS: tuple[str, ...] = (
    "yes_customer_name",
    "region_manager",
)
_PC_DRAWING_CONTRACT_FILL_FIELDS: tuple[str, ...] = (
    *_PC_DRAWING_ONLY_FILL_FIELDS,
    *_PC_SHARED_CONTRACT_FILL_FIELDS,
)
_PC_YES_CONTRACT_FILL_FIELDS: tuple[str, ...] = (
    *_PC_YES_ONLY_FILL_FIELDS,
    *_PC_SHARED_CONTRACT_FILL_FIELDS,
)
# 简道云 linkfield 展示字段在 JDY 里 available_on_create=false；CRM 发起页选合同后需同区展示
_PROD_CARD_CONTRACT_FILL_ON_CREATE_IDS: frozenset[str] = frozenset({
    *_PC_DRAWING_ONLY_FILL_FIELDS,
    *_PC_YES_ONLY_FILL_FIELDS,
    *_PC_SHARED_CONTRACT_FILL_FIELDS,
    "contract_tech_review_sn",
})


def ensure_prod_card_contract_fill_on_create(defs: list) -> None:
    """选合同带出字段在发起页可见（只读），对齐简道云选完合同后同区展示。"""
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid not in _PROD_CARD_CONTRACT_FILL_ON_CREATE_IDS:
            continue
        f["available_on_create"] = True
        f["fill_stage"] = "initiator"
        f["form_editable"] = False
_PC_CONTRACT_FILL_VIS_RULE_IDS = frozenset(
    [f"crm_vis_pc_contract_fill_{fid}" for fid in _PC_DRAWING_CONTRACT_FILL_FIELDS]
    + [f"crm_vis_pc_yes_contract_fill_{fid}" for fid in _PC_YES_CONTRACT_FILL_FIELDS]
    + ["crm_vis_pc_contract_fill_shared_yes_customer_name", "crm_vis_pc_contract_fill_shared_region_manager"]
)
_PC_CONTRACT_DISPLAY_FIELD_DEFS: tuple[dict[str, Any], ...] = (
    {"id": "contract_delivery_date", "type": "text", "label": "合同交货期"},
    {"id": "has_intelligence", "type": "text", "label": "是否含智能化"},
    {"id": "is_export_equipment", "type": "text", "label": "设备是否出口"},
)


def ensure_prod_card_contract_display_fields(defs: list) -> None:
    """补齐简道云 linkfield 同区展示字段（合同交货期 / 智能化 / 出口）。"""
    by_id = {f.get("id") for f in defs if isinstance(f, dict)}
    anchor = next(
        (i for i, f in enumerate(defs) if isinstance(f, dict) and f.get("id") == "no_drawing_no"),
        next((i for i, f in enumerate(defs) if isinstance(f, dict) and f.get("id") == "drawing_no_query"), len(defs)),
    )
    offset = 0
    for extra in _PC_CONTRACT_DISPLAY_FIELD_DEFS:
        if extra["id"] in by_id:
            continue
        defs.insert(anchor + 1 + offset, {
            **extra,
            "available_on_create": True,
            "fill_stage": "initiator",
        })
        offset += 1


def apply_prod_card_contract_pick_fields(defs: list) -> None:
    """把图纸编号查询/合同号选择改为 contract 类型，并挂部门过滤 + 带出模式。

    同时默认「是否为补充」=否：显隐规则在未选时会把两个选合同字段都藏掉，
    新建打开时必须能立刻看到合同下拉。
    提交人 / 所在部门默认当前用户与当前部门。
    「确认协议 / 设计指派填写」仅审批节点可见（对齐简道云，不在发起页展示）。
    补齐流程编号（简道云 sn：1.2.8 + 五位不重置；生成器曾跳过 sn 类型）。
    """
    ensure_prod_card_serial_no_field(defs)
    ensure_prod_card_contract_display_fields(defs)
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
            f["label"] = "选择合同"
            f["description"] = "从合同管理选择（对齐简道云图纸编号查询）；按所在部门过滤；选中后带出单位/图纸号/明细等。"
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
            f["label"] = "单位名称"
            f["form_editable"] = False
            props = dict(f.get("props") or {})
            props.pop("readonly", None)
            f["props"] = props
            f["description"] = f.get("description") or "由所选合同自动带出，不可手改。"
        elif fid == "yes_contract_no":
            f["form_editable"] = False
            f["description"] = f.get("description") or "由所选合同自动带出，不可手改。"
        elif fid == "yes_sales_person":
            f["label"] = f.get("label") or "（是）业务人员"
            f["form_editable"] = False
            f["description"] = "由所选合同自动带出；如有不符请及时反馈。"
        elif fid == "no_drawing_no":
            f["label"] = "图纸编号"
            f["form_editable"] = False
            f["description"] = f.get("description") or "由所选合同自动带出，不可手改。"
        elif fid == "no_sales_person":
            f["label"] = "业务人员"
            f["form_editable"] = False
            f["description"] = "由所选合同自动带出；如有不符请及时反馈。"
        elif fid in _CONTRACT_PICK_READONLY_IDS:
            f["description"] = f.get("description") or "由所选合同自动带出，不可手改。"
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
    ensure_prod_card_contract_fill_on_create(defs)


# 圈选区：仅审批可填（创建页隐藏）；字段级必填下沉到节点 field_perms
# 业务员确认：是否同意按协议/方案执行
_PROD_CARD_SALES_CONFIRM_PERMS: dict[str, str] = {
    "confirm_agreement": "required",
}
# 研管办安排：设计指派填写（安装图项目号 / 室主任0414 等）
_PROD_CARD_DESIGN_ASSIGN_PERMS: dict[str, str] = {
    "install_project_no": "editable",
    "f_0414": "required",
    "has_install_project": "required",
    "design_assignees": "required",
}
_PROD_CARD_APPROVER_ONLY: dict[str, str] = {
    **_PROD_CARD_SALES_CONFIRM_PERMS,
    **_PROD_CARD_DESIGN_ASSIGN_PERMS,
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


def _merge_node_field_perms(node: dict, want: dict[str, str]) -> bool:
    """把 want 合并进 node.field_perms；required 优先。返回是否有改动。"""
    perms = list(node.get("field_perms") or [])
    by_field = {
        str(p.get("field")): p
        for p in perms
        if isinstance(p, dict) and p.get("field")
    }
    changed = False
    for fid, access in want.items():
        cur = by_field.get(fid)
        if not cur:
            perms.append({"field": fid, "access": access})
            changed = True
        elif access == "required" and cur.get("access") != "required":
            cur["access"] = "required"
            changed = True
    if changed:
        node["field_perms"] = perms
    return changed


def apply_prod_card_sales_confirm_field_perms(nodes: list | None) -> bool:
    """业务员确认：可填「请确认是否同意按本协议约定、方案执行」（必填）。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if str(n.get("name") or "") != "业务员确认":
            continue
        if n.get("type") != "approval":
            continue
        if _merge_node_field_perms(n, _PROD_CARD_SALES_CONFIRM_PERMS):
            changed = True
    return changed


def _route_cond_is_region_manager_not_empty(cond) -> bool:
    if not isinstance(cond, dict):
        return False
    if cond.get("field") == "region_manager" and cond.get("operator") == "is_not_empty":
        return True
    for c in cond.get("cond") or []:
        if isinstance(c, dict) and _route_cond_is_region_manager_not_empty(c):
            return True
    return False


def apply_prod_card_sales_before_region(
    nodes: list | None, routes: list | None,
) -> bool:
    """生产卡：先业务员确认，再按区域经理/组长是否为空分支（对齐简道云画布 V43）。

    错误拓扑（data-hub 旧缓存 + 误补节点）：
      发起 --区域不为空--> 区域经理/组长 → 部门审批
      发起 --else--> 业务员确认 → 部门审批

    正确拓扑：
      发起 --else--> 业务员确认
      业务员确认 --区域不为空--> 区域经理/组长 → 部门审批
      业务员确认 --else--> 部门审批
    """
    if not isinstance(routes, list) or not nodes:
        return False
    by_name: dict[str, str] = {}
    start_ids: set[str] = set()
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        nid = str(n["id"])
        name = str(n.get("name") or "")
        if n.get("type") == "start" or name == "生产卡发起":
            start_ids.add(nid)
        if name and name not in by_name:
            by_name[name] = nid
    sales_id = by_name.get("业务员确认")
    region_id = by_name.get("区域经理/组长")
    dept_id = by_name.get("部门审批")
    if not sales_id or not region_id or not dept_id or not start_ids:
        return False

    excl = f"ex_{sales_id}"
    changed = False
    has_sales_to_dept = False
    has_sales_to_region = False

    for r in routes:
        if not isinstance(r, dict) or r.get("always"):
            continue
        src = str(r.get("source") or "")
        tgt = str(r.get("target") or "")
        cond = r.get("condition")

        # 发起→区域经理（区域不为空）→ 改挂业务员确认
        if (
            src in start_ids
            and tgt == region_id
            and _route_cond_is_region_manager_not_empty(cond)
        ):
            r["source"] = sales_id
            r["exclusive_group"] = excl
            r.pop("fork", None)
            changed = True
            has_sales_to_region = True
            continue

        if src == sales_id and tgt == region_id:
            has_sales_to_region = True
            if r.get("exclusive_group") != excl:
                r["exclusive_group"] = excl
                changed = True
            if r.get("fork") == "parallel":
                r.pop("fork", None)
                changed = True
            continue

        if src == sales_id and tgt == dept_id:
            has_sales_to_dept = True
            if r.get("exclusive_group") != excl:
                r["exclusive_group"] = excl
                changed = True
            if r.get("fork") == "parallel":
                r.pop("fork", None)
                changed = True
            continue

        # 发起仍直达部门审批（旧 else）→ 改到业务员确认
        if src in start_ids and tgt == dept_id and not cond:
            r["target"] = sales_id
            changed = True

    if not has_sales_to_region:
        routes.append({
            "id": "r_sales_to_region",
            "source": sales_id,
            "target": region_id,
            "condition": {
                "field": "region_manager",
                "operator": "is_not_empty",
                "value": None,
            },
            "exclusive_group": excl,
        })
        changed = True

    if not has_sales_to_dept:
        routes.append({
            "id": "r_sales_to_dept",
            "source": sales_id,
            "target": dept_id,
            "exclusive_group": excl,
        })
        changed = True

    # 互斥组内：有条件的区域边排在 else 前，避免 else 抢先
    sales_outs = [
        r for r in routes
        if isinstance(r, dict)
        and not r.get("always")
        and str(r.get("source") or "") == sales_id
    ]
    if len(sales_outs) >= 2:
        def _rank(r: dict) -> tuple:
            if str(r.get("target") or "") == region_id:
                return (0, 0)
            if r.get("condition"):
                return (1, 0)
            return (2, 0)

        ordered = sorted(sales_outs, key=_rank)
        if [id(r) for r in ordered] != [id(r) for r in sales_outs]:
            new_routes: list = []
            replaced = False
            for r in routes:
                if not isinstance(r, dict):
                    new_routes.append(r)
                    continue
                if r.get("always") or str(r.get("source") or "") != sales_id:
                    new_routes.append(r)
                    continue
                if not replaced:
                    new_routes.extend(ordered)
                    replaced = True
            routes[:] = new_routes
            changed = True

    return changed


def apply_prod_card_design_assign_field_perms(nodes: list | None) -> bool:
    """研管办安排节点补上安装图项目号 / 室主任0414 等可写权限。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        name = str(n.get("name") or "")
        if "研管办安排" not in name:
            continue
        if _merge_node_field_perms(n, _PROD_CARD_DESIGN_ASSIGN_PERMS):
            changed = True
        # 协议确认已归业务员确认，从研管办节点去掉避免重复必填
        perms = list(n.get("field_perms") or [])
        pruned = [
            p for p in perms
            if not (isinstance(p, dict) and p.get("field") == "confirm_agreement")
        ]
        if len(pruned) != len(perms):
            n["field_perms"] = pruned
            changed = True
    return changed


def build_prod_card_fill_from_tar(*, review_code: str | None) -> dict[str, Any]:
    """生产卡选技术协议评审后的带出（对齐简道云 linkDataMaps：仅流水号）。"""
    return {"contract_tech_review_sn": (review_code or "").strip()}


def prod_card_tar_fill_clear_keys() -> list[str]:
    return ["contract_tech_review_sn"]


async def enrich_prod_card_fill_with_region_manager(
    db,
    tenant_id: str,
    fill: dict[str, Any],
    user: dict | None = None,
) -> dict[str, Any]:
    """选合同带出业务员后，按对照表补区域经理/组长。"""
    sp = fill.get("no_sales_person") or fill.get("yes_sales_person")
    if not sp:
        return fill
    from app.domains.lowcode.salesperson_region import resolve_region_manager

    rm = await resolve_region_manager(db, tenant_id, str(sp), user)
    rm_id = rm.get("region_manager_id")
    if not rm_id:
        return fill
    out = dict(fill)
    out["region_manager"] = rm_id
    return out


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


def apply_prod_card_contract_fill_visibility(
    rules: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """选合同后同区展示（对齐简道云）：否=整块合同信息；是=合同号/业务员/单位名称。"""
    strip_ids = set(_PC_CONTRACT_FILL_VIS_RULE_IDS)
    # 去掉简道云旧规则，避免「是/否」与「已选合同」条件冲突
    for fid in _PC_DRAWING_ONLY_FILL_FIELDS:
        strip_ids.add(f"jdy_vis_{fid}")
        strip_ids.add(f"crm_vis_prod_notice_{fid}")
    for fid in _PC_YES_ONLY_FILL_FIELDS + _PC_SHARED_CONTRACT_FILL_FIELDS:
        strip_ids.add(f"jdy_vis_{fid}")
    for prefix in ("jdy_vis_yes_contract_no", "jdy_vis_yes_sales_person", "jdy_vis_yes_customer_name"):
        strip_ids.add(prefix)
    out: list[dict[str, Any]] = [
        r for r in (rules or [])
        if isinstance(r, dict) and r.get("id") not in strip_ids
    ]
    when_drawing_picked = {
        "rel": "and",
        "cond": [
            {"field": "is_supplement", "operator": "in", "value": ["否"]},
            {"field": "drawing_no_query", "operator": "is_not_empty"},
        ],
    }
    when_yes_contract_picked = {
        "rel": "and",
        "cond": [
            {"field": "is_supplement", "operator": "in", "value": ["是"]},
            {"field": "contract_no_select", "operator": "is_not_empty"},
        ],
    }
    when_either_contract_picked = {
        "rel": "or",
        "cond": [dict(when_drawing_picked), dict(when_yes_contract_picked)],
    }
    for fid in _PC_DRAWING_ONLY_FILL_FIELDS:
        out.append({
            "id": f"crm_vis_pc_contract_fill_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(when_drawing_picked),
            "action": {"visible": True},
            "enabled": True,
        })
    for fid in _PC_YES_ONLY_FILL_FIELDS:
        out.append({
            "id": f"crm_vis_pc_yes_contract_fill_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(when_yes_contract_picked),
            "action": {"visible": True},
            "enabled": True,
        })
    for fid, rid in (
        ("yes_customer_name", "crm_vis_pc_contract_fill_shared_yes_customer_name"),
        ("region_manager", "crm_vis_pc_contract_fill_shared_region_manager"),
    ):
        out.append({
            "id": rid,
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(when_either_contract_picked),
            "action": {"visible": True},
            "enabled": True,
        })
    return out


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
    return apply_prod_card_contract_fill_visibility(out)
